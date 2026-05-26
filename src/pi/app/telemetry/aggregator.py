"""Agregador de telemetria: monta o contrato (2) a partir do estado do robô.

Combina estado da máquina de estados, velocidades das rodas (sensores), roll/pitch
(Kalman), saída de visão e leituras de bateria numa única `Telemetry` para envio ao
frontend @20 Hz.

[ref: Seção 6 da AGENTS.md]
"""

from __future__ import annotations

from app.models import (
    Battery,
    ImuAngles,
    Mode,
    Telemetry,
    VisionState,
    WheelSpeeds,
)


def build_telemetry(
    estado: Mode,
    rodas: WheelSpeeds,
    imu: ImuAngles,
    visao: VisionState,
    bateria: Battery,
    ts_ms: int,
) -> Telemetry:
    """Monta o pacote de telemetria (contrato 2).

    Args:
        estado: estado atual da máquina de estados.
        rodas: velocidades medidas das rodas (rad/s).
        imu: roll/pitch filtrados (graus).
        visao: detecção/pose da tag.
        bateria: leituras do BMS (ou campos null).
        ts_ms: timestamp do Pi (ms).

    Returns:
        Telemetry pronto para serialização e envio.
    """
    raise NotImplementedError
