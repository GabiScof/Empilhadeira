"""Visão sintética: calcula pose de tags a partir do mundo simulado.

Substitui o detector de AprilTag real no modo SIM=1. Simula FOV, alcance,
ruído, motion blur, drop e perda por campo de visão.

Suporta múltiplas tags (do mapa carregado).

Unidades internas: SI (metros, radianos).

[ref: Seção 6 e 7 do mega-prompt]
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from app import config
from app.models import VisionState

if TYPE_CHECKING:
    from app.sim.world import SimTag, SimWorld


class TagDetection:
    """Resultado de detecção de uma tag individual."""
    def __init__(
        self,
        tag_id: int,
        position_id: str,
        z_m: float,
        x_m: float,
        yaw_rad: float,
        quality: float,
    ) -> None:
        self.tag_id = tag_id
        self.position_id = position_id
        self.z_m = z_m
        self.x_m = x_m
        self.yaw_rad = yaw_rad
        self.quality = quality


class SyntheticVision:
    """Fonte de visão sintética com suporte a múltiplas tags e degradações."""

    def __init__(self, seed: int = config.SIM_DEFAULT_SEED) -> None:
        self._rng = random.Random(seed)
        self._tag_hidden = False
        self._blur_prob = config.SIM_VISION_BLUR_PROB
        self._drop_prob = config.SIM_VISION_DROP_PROB
        self._fov_h_deg = config.SIM_VISION_FOV_H_DEG
        self._min_range_m = config.SIM_VISION_MIN_RANGE / 100.0
        self._max_range_m = config.SIM_VISION_MAX_RANGE / 100.0
        self._noise_std_m = config.SIM_VISION_NOISE_STD_CM / 100.0
        self._noise_std_rad = math.radians(config.SIM_VISION_NOISE_STD_DEG)

    def compute_all(self, world: "SimWorld") -> list[TagDetection]:
        """Detecta todas as tags visíveis a partir da pose atual do robô.

        Returns:
            Lista de TagDetection para cada tag visível.
        """
        if self._tag_hidden:
            return []

        if self._rng.random() < self._drop_prob:
            return []

        is_blurred = self._rng.random() < self._blur_prob

        rx_m, ry_m, rtheta = world._pose_m()
        detections: list[TagDetection] = []
        for tag in world.tags:
            det = self._compute_single(
                rx_m, ry_m, rtheta,
                tag, is_blurred,
            )
            if det is not None:
                detections.append(det)

        return detections

    def compute_legacy(self, world: "SimWorld") -> VisionState:
        """Retorna VisionState legado (primeira tag mais próxima) para compat."""
        detections = self.compute_all(world)
        if not detections:
            return VisionState()

        best = min(detections, key=lambda d: d.z_m)
        z_cm = best.z_m * 100.0
        x_cm = best.x_m * 100.0
        pitch_deg = math.degrees(best.yaw_rad)
        pitch_deg = ((pitch_deg + 180) % 360) - 180

        return VisionState(
            detectado=True,
            id=best.tag_id,
            z_cm=round(z_cm, 2),
            x_cm=round(x_cm, 2),
            pitch_deg=round(pitch_deg, 2),
        )

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
        """Calcula VisionState a partir de poses (cm) — compat legado."""
        from app.sim.world import SimTag, SimWorld

        world = SimWorld(
            robot_x=robot_x,
            robot_y=robot_y,
            robot_theta=robot_theta,
            tag_x=tag_x,
            tag_y=tag_y,
            tag_theta=tag_theta,
            tag_id=tag_id,
        )
        return self.compute_legacy(world)

    def _compute_single(
        self,
        robot_x: float, robot_y: float, robot_theta: float,
        tag: "SimTag",
        is_blurred: bool,
    ) -> TagDetection | None:
        """Computa detecção de uma única tag."""
        dx = tag.x_m - robot_x
        dy = tag.y_m - robot_y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < self._min_range_m or distance > self._max_range_m:
            return None

        angle_to_tag = math.atan2(dy, dx)
        relative_angle = angle_to_tag - robot_theta
        relative_angle = math.atan2(math.sin(relative_angle), math.cos(relative_angle))

        half_fov = math.radians(self._fov_h_deg / 2.0)
        if abs(relative_angle) > half_fov:
            return None

        z_m = distance * math.cos(relative_angle)
        x_m = distance * math.sin(relative_angle)

        yaw_rel = (tag.yaw_rad - robot_theta) - math.pi
        yaw_rel = math.atan2(math.sin(yaw_rel), math.cos(yaw_rel))

        quality = 1.0
        if is_blurred:
            quality = 0.3
            if self._rng.random() < 0.5:
                return None

        noise_scale = 1.0 / max(quality, 0.1)
        z_m += self._rng.gauss(0, self._noise_std_m * noise_scale)
        x_m += self._rng.gauss(0, self._noise_std_m * noise_scale)
        yaw_rel += self._rng.gauss(0, self._noise_std_rad * noise_scale)

        return TagDetection(
            tag_id=tag.april_tag_id,
            position_id=tag.position_id,
            z_m=z_m,
            x_m=x_m,
            yaw_rad=yaw_rel,
            quality=quality,
        )

    def set_tag_hidden(self, hidden: bool) -> None:
        self._tag_hidden = hidden

    def set_blur_prob(self, prob: float) -> None:
        self._blur_prob = max(0.0, min(1.0, prob))

    def set_drop_prob(self, prob: float) -> None:
        self._drop_prob = max(0.0, min(1.0, prob))
