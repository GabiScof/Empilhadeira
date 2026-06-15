"""Tarefa de controle: navegação + máquina de estados → setpoint, a 20 Hz.

Roda **independente** da cadência de comando do operador. O frontend é orientado a
evento (envia comando só quando o operador age), então o controle de malha fechada
NÃO pode viver no loop de recepção do WebSocket — senão, em AUTOMATICO, o robô
receberia um único setpoint e congelaria.

A cada tick:
1. Lê a intenção do operador (último comando) e a última visão do estado.
2. Propõe velocidades de roda via cinemática (MANUAL) ou navegação (AUTOMATICO).
3. Passa pela máquina de estados (perda de tag → PARADO, latch de segurança).
4. Aplica o watchdog de comando do MANUAL.
5. Escreve o `current_setpoint` que o serial_loop envia ao ESP32.

[ref: Seção 2 e 7 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import logging
import time

from app import config
from app.control.kinematics import joystick_to_twist, twist_to_wheel_speeds
from app.models import ForkCommand, Mode, Setpoint, VisionState
from app.state import SharedState

logger = logging.getLogger(__name__)


def _propose_wheel_speeds(
    requested_mode: Mode,
    vision: VisionState,
    joystick_x: float,
    joystick_y: float,
    state: SharedState,
) -> tuple[float, float]:
    """Propõe (w_esq, w_dir) em rad/s para o modo pedido, antes da máquina de estados."""
    if requested_mode == Mode.MANUAL:
        v, omega = joystick_to_twist(joystick_x, joystick_y)
        return twist_to_wheel_speeds(v, omega)

    if requested_mode == Mode.AUTOMATICO:
        if not vision.detectado:
            return 0.0, 0.0
        v, omega = state.navigator.compute(
            z_cm=vision.z_cm or 0.0,
            x_cm=vision.x_cm or 0.0,
            pitch_deg=vision.pitch_deg or 0.0,
        )
        return twist_to_wheel_speeds(v, omega)

    return 0.0, 0.0


async def control_loop(state: SharedState) -> None:
    """Loop de controle de malha fechada a `config.CONTROL_HZ`."""
    logger.info("Control loop iniciado (%.0f Hz)", config.CONTROL_HZ)
    interval = 1.0 / config.CONTROL_HZ

    try:
        while True:
            current_time_ms = int(time.time() * 1000)

            async with state.lock:
                command = state.last_command
                vision = state.last_vision

            if command is None:
                # Sem operador conectado/agindo: estado seguro.
                requested_mode = Mode.PARADO
                joystick_x = joystick_y = 0.0
                garfo = ForkCommand.PARAR
            else:
                requested_mode = command.modo
                joystick_x = command.joystick.x
                joystick_y = command.joystick.y
                garfo = command.garfo

            w_esq, w_dir = _propose_wheel_speeds(
                requested_mode, vision, joystick_x, joystick_y, state
            )

            mode, w_esq, w_dir, garfo = state.state_machine.step(
                requested_mode=requested_mode,
                vision=vision,
                garfo=garfo,
                current_time_ms=current_time_ms,
                w_esq=w_esq,
                w_dir=w_dir,
            )

            if state.state_machine.check_command_watchdog(current_time_ms):
                w_esq, w_dir = 0.0, 0.0
                logger.warning("Watchdog de comando disparou → PARADO")

            await state.update_setpoint(Setpoint(w_esq=w_esq, w_dir=w_dir, garfo=garfo))

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Control loop cancelado")
