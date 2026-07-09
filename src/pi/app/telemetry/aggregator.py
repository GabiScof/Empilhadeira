"""Agregador de telemetria: monta o contrato (2) a partir do estado do robô."""

from __future__ import annotations

from app.models import (
    Battery,
    DetectedTag,
    EkfState,
    ImuAngles,
    MissionInfo,
    Mode,
    NavigationInfo,
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
    parado_reason: str | None = None,
    nav_phase: str | None = None,
    ekf: EkfState | None = None,
    mission: MissionInfo | None = None,
    navigation: NavigationInfo | None = None,
    detected_tags: list[DetectedTag] | None = None,
    map_name: str | None = None,
) -> Telemetry:
    """Monta o pacote de telemetria (contrato 2 estendido)."""
    return Telemetry(
        estado=estado,
        rodas=rodas,
        imu=imu,
        visao=visao,
        bateria=bateria,
        ts_ms=ts_ms,
        parado_reason=parado_reason,
        nav_phase=nav_phase,
        ekf=ekf,
        mission=mission,
        navigation=navigation,
        detected_tags=detected_tags or [],
        map_name=map_name,
    )
