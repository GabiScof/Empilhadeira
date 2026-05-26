"""Schemas Pydantic dos 4 contratos de interface do sistema.

Este módulo é o **espelho Python** da fonte única de verdade definida em
`docs/serial-protocol.md`. Qualquer mudança de contrato deve ser refletida
simultaneamente aqui, em `firmware/src/protocol.*` (C++) e em
`frontend/src/types/contracts.ts` (TypeScript).

Convenções (ver doc):
- Velocidade angular de roda em **rad/s**.
- Ângulos em **graus**; distâncias em **cm**; corrente em **A**; temperatura em °C.
- Timestamps em **ms** (int).

[ref: Seção 6 da AGENTS.md]
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Mode(StrEnum):
    """Modo de operação pedido pelo operador / estado da máquina de estados."""

    MANUAL = "MANUAL"
    AUTOMATICO = "AUTOMATICO"
    PARADO = "PARADO"


class ForkCommand(StrEnum):
    """Comando do garfo (canal independente, sempre manual)."""

    SUBIR = "subir"
    DESCER = "descer"
    PARAR = "parar"


# ---------------------------------------------------------------------------
# Contrato (1) — Frontend → Pi · comando (WebSocket)
# ---------------------------------------------------------------------------
class Joystick(BaseModel):
    """Posição do joystick virtual. Componentes em [-1, 1]. Só vale em MANUAL."""

    x: float = Field(0.0, ge=-1.0, le=1.0, description="Giro (ω), adimensional.")
    y: float = Field(0.0, ge=-1.0, le=1.0, description="Avanço (v), adimensional.")


class Command(BaseModel):
    """Comando enviado pelo frontend ao Pi via WebSocket.

    Campos:
        modo: estado desejado pelo operador.
        joystick: posição do joystick (ignorada fora de MANUAL).
        garfo: comando do garfo (vale nos dois modos).
        ts_ms: timestamp do cliente em ms (usado no watchdog de comando).
    """

    modo: Mode
    joystick: Joystick = Field(default_factory=Joystick)
    garfo: ForkCommand = ForkCommand.PARAR
    ts_ms: int = Field(0, ge=0)


# ---------------------------------------------------------------------------
# Contrato (2) — Pi → Frontend · telemetria @20Hz (WebSocket)
# ---------------------------------------------------------------------------
class WheelSpeeds(BaseModel):
    """Velocidades angulares medidas das rodas, em rad/s."""

    esq: float = Field(description="Roda esquerda (rad/s).")
    dir: float = Field(description="Roda direita (rad/s).")


class ImuAngles(BaseModel):
    """Orientação filtrada (Kalman) em graus."""

    roll: float = Field(description="Roll (graus).")
    pitch: float = Field(description="Pitch (graus).")


class VisionState(BaseModel):
    """Saída da visão (detecção + pose da AprilTag). Campos null sem detecção."""

    detectado: bool = False
    id: int | None = None
    z_cm: float | None = Field(None, description="Distância ao alvo (cm).")
    x_cm: float | None = Field(None, description="Deslocamento lateral (cm).")
    pitch_deg: float | None = Field(None, description="Orientação relativa da tag (graus).")


class Battery(BaseModel):
    """Leituras de bateria. Campos null se o BMS não tiver leitura digital."""

    cel: float | None = Field(
        None, description="Tensão de célula. TODO(equipe): confirmar unidade (V?)."
    )
    i_a: float | None = Field(None, description="Corrente (A).")
    temp_c: float | None = Field(None, description="Temperatura (°C).")


class Telemetry(BaseModel):
    """Telemetria enviada pelo Pi ao frontend @20 Hz.

    Campos:
        estado: estado real da máquina de estados (não o pedido).
        rodas: velocidades medidas das rodas (rad/s).
        imu: roll/pitch filtrados (graus).
        visao: detecção e pose da tag.
        bateria: leituras do BMS (ou null).
        ts_ms: timestamp do Pi (ms).
    """

    estado: Mode
    rodas: WheelSpeeds
    imu: ImuAngles
    visao: VisionState = Field(default_factory=VisionState)
    bateria: Battery = Field(default_factory=Battery)
    ts_ms: int = Field(0, ge=0)


# ---------------------------------------------------------------------------
# Contrato (3) — Pi → ESP32 · setpoint (UART, emoldurado)
# ---------------------------------------------------------------------------
class Setpoint(BaseModel):
    """Setpoint de velocidade das rodas + comando do garfo, enviado ao ESP32.

    Campos:
        w_esq: velocidade alvo da roda esquerda (rad/s).
        w_dir: velocidade alvo da roda direita (rad/s).
        garfo: comando do garfo, repassado direto ao motor.
    """

    w_esq: float = Field(description="Setpoint roda esquerda (rad/s).")
    w_dir: float = Field(description="Setpoint roda direita (rad/s).")
    garfo: ForkCommand = ForkCommand.PARAR


# ---------------------------------------------------------------------------
# Contrato (4) — ESP32 → Pi · sensores (UART, emoldurado)
# ---------------------------------------------------------------------------
class Encoders(BaseModel):
    """Velocidades medidas pelos encoders, em rad/s."""

    esq: float = Field(description="Encoder esquerdo (rad/s).")
    dir: float = Field(description="Encoder direito (rad/s).")


class MpuRaw(BaseModel):
    """Leituras **cruas** do MPU-6050. A fusão (Kalman) é feita no Pi."""

    ax: float = Field(description="Aceleração X (m/s²).")
    ay: float = Field(description="Aceleração Y (m/s²).")
    az: float = Field(description="Aceleração Z (m/s²).")
    gx: float = Field(description="Velocidade angular X (graus/s).")
    gy: float = Field(description="Velocidade angular Y (graus/s).")
    gz: float = Field(description="Velocidade angular Z (graus/s).")
    temp_c: float = Field(description="Temperatura (°C).")


class Sensors(BaseModel):
    """Pacote de sensores enviado pelo ESP32 ao Pi.

    Campos:
        enc: velocidades dos encoders (rad/s).
        mpu: leituras cruas do MPU-6050.
        bms: leituras de bateria (mesmo formato de Battery) ou null.
    """

    enc: Encoders
    mpu: MpuRaw
    bms: Battery | None = None
