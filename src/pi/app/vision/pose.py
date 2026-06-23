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
from app.hardware.interfaces import TagObservation
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


def estimate_tag_observations(detections: list[Any]) -> list[TagObservation]:
    """Converte detecções cruas em ``TagObservation`` (relativas) para o EKF.

    A posição relativa (``x_m``, ``z_m``) vem direto da translação estimada e é
    confiável. O ``yaw_rad`` segue a convenção esperada pelo EKF (ver
    ``TagObservation``); como o pitch de uma única tag pequena tem ambiguidade,
    a correção de **heading** deve ser validada no hardware real.

    ``position_id`` fica vazio aqui — quem resolve o ID lógico contra o mapa é o
    ``vision_loop`` (via ``world_model``).

    [ref: pose.py:estimate_vision_state; TODO(equipe): validar convenção de yaw]
    """
    observations: list[TagObservation] = []
    for det in detections:
        pose_t = np.asarray(det.pose_t).reshape(-1)
        pose_r = np.asarray(det.pose_R)

        x_m, _y_m, z_m = (float(pose_t[0]), float(pose_t[1]), float(pose_t[2]))
        _roll_deg, pitch_deg, _yaw_deg = rotation_matrix_to_euler_angles(pose_r)

        # Convenção do EKF: yaw_rad = (yaw_tag_mundo - theta_robô) - π.
        # TODO(equipe): confirmar sinal/eixo contra o frame real da câmera.
        yaw_rad = math.radians(float(pitch_deg)) - math.pi

        quality = float(getattr(det, "decision_margin", 0.0))
        quality = max(0.0, min(1.0, quality / 100.0)) if quality else 1.0

        observations.append(
            TagObservation(
                tag_id=int(det.tag_id),
                position_id="",
                z_m=z_m,
                x_m=x_m,
                yaw_rad=yaw_rad,
                quality=quality,
            )
        )
    return observations
