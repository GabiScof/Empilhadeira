"""Tarefa serial: troca setpoint/sensores com o ESP32 via UART @20 Hz.

Responsabilidades:
- Calcular o setpoint (contrato 3) a partir do estado (manual: cinemática do
  joystick; automático: navegação) e enviá-lo emoldurado (JSON+CRC8+\\n).
- Receber e decodificar sensores (contrato 4), atualizar o estado compartilhado.
- Aplicar a fusão de Kalman sobre o MPU cru → roll/pitch.
- **Watchdog serial**: se a serial cair, o ESP32 zera os motores localmente; o Pi
  deve detectar a ausência de sensores e refletir estado seguro. [ref: Seção 7]

Usa `pyserial-asyncio`. [ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import logging
import math

import serial_asyncio

from app.comms.protocol import SensorsFrameDecoder, encode_setpoint
from app.config import SERIAL_BAUDRATE, SERIAL_HZ, SERIAL_LOST_FRAMES, SERIAL_PORT
from app.control.kalman import AttitudeKalman
from app.control.kinematics import joystick_to_twist, twist_to_wheel_speeds
from app.control.navigation import compute_twist_primary
from app.models import ForkCommand, ImuAngles, Mode, MpuRaw, Sensors, Setpoint
from app.state import SharedState

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Funções auxiliares (nível de módulo — sem acesso ao estado)
# ---------------------------------------------------------------------------

def _accel_angles(mpu: MpuRaw) -> ImuAngles:
    """Estimativa de roll/pitch via acelerômetro (fallback enquanto Kalman é stub).

    Usa apenas o vetor de gravidade medido pelo acelerômetro para derivar a
    inclinação. É ruidoso sob vibração, mas serve de placeholder até o filtro
    de Kalman ser implementado em app/control/kalman.py.

    Fórmulas:
        roll  = atan2(ay, az)          — rotação em torno do eixo X
        pitch = atan2(-ax, √(ay²+az²)) — rotação em torno do eixo Y
    """
    roll = math.degrees(math.atan2(mpu.ay, mpu.az))
    pitch = math.degrees(math.atan2(-mpu.ax, math.sqrt(mpu.ay**2 + mpu.az**2)))
    return ImuAngles(roll=roll, pitch=pitch)


def _compute_setpoint(state: SharedState) -> Setpoint:
    """Deriva o setpoint de velocidade de roda (contrato 3) a partir do modo atual.

    Fluxo por modo:
      MANUAL     → joystick (x, y) ∈ [-1,1]
                     └─ joystick_to_twist()  →  (v cm/s, ω rad/s)
                     └─ twist_to_wheel_speeds()  →  (w_esq, w_dir) rad/s
      AUTOMATICO → pose da AprilTag (VisionState)
                     └─ compute_twist_primary()  →  (v, ω)
                     └─ twist_to_wheel_speeds()  →  (w_esq, w_dir) rad/s
      PARADO     → zeros (rodas paradas)

    Enquanto kinematics/navigation são stubs (NotImplementedError), o bloco
    except captura o erro e manda zeros — comportamento seguro sem travar o loop.

    O campo `garfo` vem sempre do último Command do operador, independente do modo,
    porque é um canal independente (ver contrato 1).
    """
    # Garfo: lê do último comando; se nenhum comando chegou ainda, para o garfo.
    garfo = ForkCommand.PARAR
    if state.last_command is not None:
        garfo = state.last_command.garfo

    if state.mode == Mode.MANUAL and state.last_command is not None:
        # Modo manual: converte o joystick em velocidades de roda via cinemática diferencial.
        try:
            v, omega = joystick_to_twist(
                state.last_command.joystick.x,
                state.last_command.joystick.y,
            )
            w_esq, w_dir = twist_to_wheel_speeds(v, omega)
        except NotImplementedError:
            _log.debug("[SERIAL] kinematics stub: setpoint manual zerado")
            w_esq, w_dir = 0.0, 0.0

    elif state.mode == Mode.AUTOMATICO:
        # Modo automático: navegação proporcional baseada na pose da AprilTag detectada.
        try:
            v, omega = compute_twist_primary(state.last_vision)
            w_esq, w_dir = twist_to_wheel_speeds(v, omega)
        except NotImplementedError:
            _log.debug("[SERIAL] navigation stub: setpoint automático zerado")
            w_esq, w_dir = 0.0, 0.0

    else:
        # PARADO (ou MANUAL sem comando ainda): motores parados.
        w_esq, w_dir = 0.0, 0.0

    return Setpoint(w_esq=w_esq, w_dir=w_dir, garfo=garfo)


# ---------------------------------------------------------------------------
# Tarefa principal
# ---------------------------------------------------------------------------

async def serial_loop(state: SharedState) -> None:
    """Loop da tarefa serial (setpoint out / sensores in).

    Args:
        state: estado compartilhado entre as tarefas.
    """

    # --- Abertura da porta UART ------------------------------------------------
    # open_serial_connection() devolve um par (StreamReader, StreamWriter) da
    # biblioteca pyserial-asyncio — mesma interface de asyncio.open_connection(),
    # mas sobre uma porta serial física em vez de um socket TCP.
    _log.info("[SERIAL] abrindo %s @ %d baud", SERIAL_PORT, SERIAL_BAUDRATE)
    reader, writer = await serial_asyncio.open_serial_connection(
        url=SERIAL_PORT, baudrate=SERIAL_BAUDRATE
    )
    _log.info("[SERIAL] porta aberta")

    # --- Inicialização do filtro de Kalman ------------------------------------
    # AttitudeKalman ainda é um stub (NotImplementedError no __init__). Se falhar,
    # operamos com o fallback de acelerômetro (_accel_angles) até ser implementado.
    try:
        kalman: AttitudeKalman | None = AttitudeKalman()
    except NotImplementedError:
        kalman = None
        _log.warning("[SERIAL] AttitudeKalman stub: usando fallback de acelerômetro")

    # --- Variáveis de controle do loop ----------------------------------------
    decoder = SensorsFrameDecoder()      # acumula bytes e separa frames por '\n'
    loop = asyncio.get_running_loop()
    interval: float = 1.0 / SERIAL_HZ   # ~50 ms entre cada ciclo a 20 Hz
    serial_timeout_s: float = SERIAL_LOST_FRAMES / SERIAL_HZ  # ~250 ms sem sensor → PARADO

    # Timestamps monótonos usados pelo watchdog e pelo Kalman.
    last_sensor_at: float = loop.time()  # instante do último pacote de sensor válido
    last_kalman_at: float = loop.time()  # instante da última atualização do Kalman

    # --- Função auxiliar de fusão sensorial ------------------------------------
    def _apply_kalman(sensors: Sensors) -> None:
        """Aplica o Kalman (ou fallback) e atualiza state.last_imu."""
        nonlocal kalman, last_kalman_at
        # dt_s é o tempo REAL desde a última chamada — importante para a
        # equação de predição do Kalman; usar o período nominal seria errado
        # se houver jitter ou frames descartados.
        now = loop.time()
        dt_s = now - last_kalman_at
        last_kalman_at = now
        mpu = sensors.mpu
        if kalman is not None:
            try:
                imu = kalman.update(mpu, dt_s)
            except NotImplementedError:
                # Kalman foi instanciado mas update() ainda não foi implementado:
                # desativa para não repetir o erro a cada frame.
                kalman = None
                imu = _accel_angles(mpu)
        else:
            imu = _accel_angles(mpu)
        state.update_imu(imu)

    # --- Sub-loop de envio (Pi → ESP32, @20 Hz) --------------------------------
    async def _send() -> None:
        """Calcula e envia o setpoint para o ESP32 a cada ciclo."""
        while True:
            t0 = loop.time()

            # Watchdog serial: se o _receive não atualizou last_sensor_at por
            # mais de serial_timeout_s, considera a UART morta e força PARADO.
            # O ESP32 tem seu próprio watchdog de setpoint e também zerará os
            # motores, mas o Pi precisa refletir o estado seguro localmente.
            if loop.time() - last_sensor_at > serial_timeout_s:
                if state.mode != Mode.PARADO:
                    _log.warning(
                        "[SERIAL] watchdog: sem sensores por %.0f ms → PARADO",
                        serial_timeout_s * 1000,
                    )
                    state.set_mode(Mode.PARADO)

            # Monta e serializa o setpoint: JSON compacto + '*' + CRC8 hex + '\n'
            setpoint = _compute_setpoint(state)
            writer.write(encode_setpoint(setpoint))
            await writer.drain()   # garante que os bytes saíram do buffer do SO

            # Dorme o tempo restante do ciclo para manter ~20 Hz mesmo que
            # _compute_setpoint() ou writer.drain() consumam alguns milissegundos.
            await asyncio.sleep(max(0.0, interval - (loop.time() - t0)))

    # --- Sub-loop de recepção (ESP32 → Pi, contínuo) ---------------------------
    async def _receive() -> None:
        """Lê frames de sensor da UART, decodifica e atualiza o estado."""
        nonlocal last_sensor_at
        while True:
            # readline() aguarda até encontrar '\n' (fim de frame serial).
            # O timeout de 3 ciclos (~150 ms) evita travar indefinidamente caso
            # o ESP32 pare de enviar dados — a próxima iteração tentará de novo
            # e o watchdog em _send() detectará a ausência prolongada.
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=interval * 3)
            except asyncio.TimeoutError:
                _log.debug("[SERIAL] readline timeout (sem frame em %.0f ms)", interval * 3000)
                continue

            # SensorsFrameDecoder valida CRC e schema; devolve lista de Sensors
            # válidos (normalmente 0 ou 1 por readline). Frames com CRC ou JSON
            # inválidos são descartados silenciosamente pelo decoder.
            for sensors in decoder.feed(line):
                state.update_sensors(sensors)   # salva encoders + BMS no SharedState
                _apply_kalman(sensors)           # atualiza state.last_imu (roll/pitch)
                last_sensor_at = loop.time()     # "pulsa" o watchdog

    # --- Gerenciamento do ciclo de vida das subtarefas -------------------------
    # Ambas as subtarefas rodam em paralelo (asyncio cooperativo, thread única).
    # Se qualquer uma encerrar (erro ou desconexão), encerramos a outra também.
    send_task = asyncio.create_task(_send(), name="serial-send")
    receive_task = asyncio.create_task(_receive(), name="serial-receive")
    all_subtasks = [send_task, receive_task]

    try:
        # Aguarda até a PRIMEIRA subtarefa terminar (normalmente por exceção).
        done, pending = await asyncio.wait(
            all_subtasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Cancela a outra subtarefa (que ainda estava rodando) e aguarda sua saída.
        for t in pending:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        # Loga qualquer exceção não esperada da subtarefa que terminou primeiro.
        for t in done:
            if not t.cancelled():
                exc = t.exception()
                if exc is not None:
                    _log.error("[SERIAL] exceção na subtarefa: %s", exc)
    finally:
        # finally garante limpeza tanto no fluxo normal quanto quando
        # serial_loop() é cancelada externamente (ex: desligamento do servidor).
        for t in all_subtasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*all_subtasks, return_exceptions=True)
        writer.close()                   # fecha a porta serial
        state.set_mode(Mode.PARADO)      # garante estado seguro no SharedState
        _log.info("[SERIAL] porta serial fechada; modo → PARADO")
