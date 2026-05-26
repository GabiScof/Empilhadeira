"""Estimativa de pose da AprilTag → contrato de visão (z_cm, x_cm, pitch_deg).

A partir de uma detecção com pose (translação `pose_t`, rotação `pose_R`) e do
tamanho físico da tag, converte para as grandezas do contrato de telemetria.

Limitações conhecidas a tratar na implementação [ref: Seção 4]:
- Pitch de uma única tag pequena tem **ambiguidade de pose**.
- O **offset extrínseco câmera→garfo** precisa ser aplicado (alinhar a câmera ≠
  alinhar o garfo). [ref: CAMERA_TO_FORK_OFFSET_CM em app/config.py]

[ref: Seção 7 da AGENTS.md]
"""

from __future__ import annotations

from typing import Any

from app.models import VisionState


def estimate_vision_state(detections: list[Any]) -> VisionState:
    """Converte detecções de AprilTag na `VisionState` do contrato.

    Args:
        detections: detecções cruas (com pose) do detector.

    Returns:
        VisionState com detectado/id/z_cm/x_cm/pitch_deg. Sem detecção → campos null.
    """
    raise NotImplementedError
