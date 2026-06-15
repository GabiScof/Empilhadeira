"""Visão sintética: calcula pose da tag a partir das posições do robô e pallet.

Substitui o detector de AprilTag real no modo SIM=1. Simula FOV, alcance, ruído
e perda de tag. Determinístico via PRNG com seed.

[ref: Seção 7 do mega-prompt]
"""

from __future__ import annotations

import math
import random

from app import config
from app.models import VisionState


class SyntheticVision:
    """Fonte de visão sintética baseada na geometria robô-tag."""

    def __init__(self, seed: int = config.SIM_DEFAULT_SEED) -> None:
        self._rng = random.Random(seed)
        self._tag_hidden = False

    def compute(
        self,
        robot_x: float,
        robot_y: float,
        robot_theta: float,
        tag_x: float,
        tag_y: float,
        tag_theta: float,
        tag_id: int = 0,
    ) -> VisionState:
        """Calcula VisionState a partir das poses no mundo.

        Args:
            robot_x, robot_y: posição do robô (cm).
            robot_theta: orientação do robô (rad).
            tag_x, tag_y: posição da tag (cm).
            tag_theta: orientação da tag (rad).
            tag_id: ID da tag.

        Returns:
            VisionState com detecção e pose, ou sem detecção se fora do FOV/range.
        """
        if self._tag_hidden:
            return VisionState()

        dx = tag_x - robot_x
        dy = tag_y - robot_y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < config.SIM_VISION_MIN_RANGE or distance > config.SIM_VISION_MAX_RANGE:
            return VisionState()

        angle_to_tag = math.atan2(dy, dx)
        relative_angle = angle_to_tag - robot_theta
        relative_angle = math.atan2(math.sin(relative_angle), math.cos(relative_angle))

        half_fov = math.radians(config.SIM_VISION_FOV_H_DEG / 2.0)
        if abs(relative_angle) > half_fov:
            return VisionState()

        z_cm = distance * math.cos(relative_angle)
        x_cm = distance * math.sin(relative_angle)

        pitch_deg = math.degrees(tag_theta - robot_theta)
        pitch_deg = ((pitch_deg + 180) % 360) - 180

        z_cm += self._rng.gauss(0, config.SIM_VISION_NOISE_STD_CM)
        x_cm += self._rng.gauss(0, config.SIM_VISION_NOISE_STD_CM)
        pitch_deg += self._rng.gauss(0, config.SIM_VISION_NOISE_STD_DEG)

        if abs(pitch_deg) < 2.0:
            pitch_deg += self._rng.gauss(0, config.SIM_VISION_NOISE_STD_DEG * 2)

        return VisionState(
            detectado=True,
            id=tag_id,
            z_cm=round(z_cm, 2),
            x_cm=round(x_cm, 2),
            pitch_deg=round(pitch_deg, 2),
        )

    def set_tag_hidden(self, hidden: bool) -> None:
        """Injeta/remove ocultação da tag."""
        self._tag_hidden = hidden
