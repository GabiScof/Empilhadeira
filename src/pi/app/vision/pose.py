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

import math
from typing import Any

import numpy as np

from app import config
from app.models import VisionState


def rotation_matrix_to_euler_angles(rotation_matrix: Any) -> tuple[float, float, float]:
    """Converte matriz de rotação em roll, pitch e yaw em graus."""
    sy = math.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)
    singular = sy < 1e-6

    if not singular:
        roll = math.atan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
        pitch = math.atan2(-rotation_matrix[2, 0], sy)
        yaw = math.atan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
    else:
        roll = math.atan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
        pitch = math.atan2(-rotation_matrix[2, 0], sy)
        yaw = 0.0

    roll_deg, pitch_deg, yaw_deg = np.degrees([roll, pitch, yaw])
    return float(roll_deg), float(pitch_deg), float(yaw_deg)


def estimate_vision_state(detections: list[Any]) -> VisionState:
    """Converte detecções de AprilTag na `VisionState` do contrato.

    Args:
        detections: detecções cruas (com pose) do detector.

    Returns:
        VisionState com detectado/id/z_cm/x_cm/pitch_deg. Sem detecção → campos null.
    """
    if not detections:
        return VisionState()

    best_detection = min(
        detections,
        key=lambda detection: float(np.linalg.norm(np.asarray(detection.pose_t).reshape(-1))),
    )

    pose_t = np.asarray(best_detection.pose_t).reshape(-1)
    pose_r = np.asarray(best_detection.pose_R)

    x_m, _y_m, z_m = pose_t
    _roll_deg, pitch_deg, _yaw_deg = rotation_matrix_to_euler_angles(pose_r)

    x_cm = float(x_m * 100.0)
    z_cm = float(z_m * 100.0)

    if config.CAMERA_TO_FORK_OFFSET_CM is not None:
        offset_x_cm, _offset_y_cm, offset_z_cm = config.CAMERA_TO_FORK_OFFSET_CM
        x_cm += offset_x_cm
        z_cm += offset_z_cm

    return VisionState(
        detectado=True,
        id=int(best_detection.tag_id),
        z_cm=z_cm,
        x_cm=x_cm,
        pitch_deg=float(pitch_deg),
    )
