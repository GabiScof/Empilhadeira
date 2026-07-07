"""Mundo de simulação paramétrico: arena, pose do robô e tags a partir do mapa.

Integra a cinemática diferencial a partir das velocidades das rodas para
atualizar a pose do robô. As tags vêm do mapa carregado (WorldModel).
Suporta slip de roda, ruído de encoder, drift de giroscópio.

Unidades internas: SI (metros, radianos, segundos).

[ref: Seção 7 do mega-prompt]
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app import config
from app.world.robot_model import RobotModel

if TYPE_CHECKING:
    from app.world.world_model import WorldModel


@dataclass
class SimTag:
    """Tag no mundo simulado."""
    position_id: str
    x_m: float
    y_m: float
    yaw_rad: float
    april_tag_id: int = -1


class SimWorld:
    """Mundo retangular com robô e múltiplas tags, carregado do mapa."""

    def __init__(
        self,
        world_model: "WorldModel | None" = None,
        robot_model: RobotModel | None = None,
        seed: int = config.SIM_DEFAULT_SEED,
        *,
        robot_x: float | None = None,
        robot_y: float | None = None,
        robot_theta: float | None = None,
        tag_x: float | None = None,
        tag_y: float | None = None,
        tag_theta: float | None = None,
        tag_id: int | None = None,
    ) -> None:
        self._robot_model = robot_model or RobotModel()
        self._rng = random.Random(seed)

        if world_model is not None:
            self._legacy_cm = False
            self.arena_width_m = world_model.arena_width_m
            self.arena_height_m = world_model.arena_height_m
            sx, sy, st = world_model.start_pose
            self.robot_x = sx
            self.robot_y = sy
            self.robot_theta = st
            self.tags: list[SimTag] = []
            for i, tag in enumerate(world_model.tags):
                self.tags.append(SimTag(
                    position_id=tag.position_id,
                    x_m=tag.x_m,
                    y_m=tag.y_m,
                    yaw_rad=tag.yaw_rad,
                    april_tag_id=tag.april_tag_id if tag.april_tag_id is not None else i,
                ))
            self._world_model = world_model
        elif any(v is not None for v in (robot_x, robot_y, robot_theta, tag_x, tag_y, tag_theta, tag_id)):
            # Compat legado: coordenadas externas em cm.
            self._legacy_cm = True
            self.arena_width_m = config.SIM_ARENA_WIDTH / 100.0
            self.arena_height_m = config.SIM_ARENA_HEIGHT / 100.0
            self.robot_x = robot_x if robot_x is not None else 100.0
            self.robot_y = robot_y if robot_y is not None else 150.0
            self.robot_theta = robot_theta if robot_theta is not None else -math.pi / 2
            self.tags = [SimTag(
                position_id="P0",
                x_m=(tag_x if tag_x is not None else 100.0) / 100.0,
                y_m=(tag_y if tag_y is not None else 50.0) / 100.0,
                yaw_rad=tag_theta if tag_theta is not None else math.pi / 2,
                april_tag_id=tag_id if tag_id is not None else 0,
            )]
            self._world_model = None
        else:
            self._legacy_cm = False
            self.arena_width_m = config.SIM_ARENA_WIDTH / 100.0
            self.arena_height_m = config.SIM_ARENA_HEIGHT / 100.0
            self.robot_x = 1.0
            self.robot_y = 1.5
            self.robot_theta = -math.pi / 2
            self.tags = [SimTag(
                position_id="P0",
                x_m=1.0,
                y_m=0.5,
                yaw_rad=math.pi / 2,
                april_tag_id=0,
            )]
            self._world_model = None

        self.slip_esq: float = 1.0
        self.slip_dir: float = 1.0

        self.encoder_noise_std: float = config.SIM_ENCODER_NOISE_STD
        self.gyro_drift_rads: float = config.SIM_GYRO_DRIFT_RADS

        self.trail: list[tuple[float, float]] = [(self.robot_x, self.robot_y)]

    @property
    def tag_x(self) -> float:
        """Posição X da primeira tag (cm) — compat legado."""
        return self.tags[0].x_m * 100.0 if self.tags else 0.0

    @property
    def tag_y(self) -> float:
        """Posição Y da primeira tag (cm) — compat legado."""
        return self.tags[0].y_m * 100.0 if self.tags else 0.0

    @property
    def tag_theta(self) -> float:
        """Orientação da primeira tag (rad) — compat legado."""
        return self.tags[0].yaw_rad if self.tags else 0.0

    @property
    def tag_id(self) -> int:
        """ID AprilTag da primeira tag — compat legado."""
        return self.tags[0].april_tag_id if self.tags else -1

    def _pose_m(self) -> tuple[float, float, float]:
        """Pose do robô em metros (SI)."""
        if self._legacy_cm:
            return self.robot_x / 100.0, self.robot_y / 100.0, self.robot_theta
        return self.robot_x, self.robot_y, self.robot_theta

    def _set_pose_m(self, x_m: float, y_m: float, theta: float) -> None:
        if self._legacy_cm:
            self.robot_x = x_m * 100.0
            self.robot_y = y_m * 100.0
        else:
            self.robot_x = x_m
            self.robot_y = y_m
        self.robot_theta = theta

    def step(self, w_esq: float, w_dir: float, dt: float) -> None:
        """Integra a cinemática diferencial por dt segundos.

        Args:
            w_esq: velocidade angular roda esquerda (rad/s).
            w_dir: velocidade angular roda direita (rad/s).
            dt: intervalo de tempo (s).
        """
        w_esq_eff = w_esq * self.slip_esq
        w_dir_eff = w_dir * self.slip_dir

        x_m, y_m, theta = self._pose_m()
        x_m, y_m, theta = self._robot_model.diff_drive_step(
            x_m, y_m, theta,
            w_esq_eff, w_dir_eff, dt,
        )

        x_m = max(0, min(self.arena_width_m, x_m))
        y_m = max(0, min(self.arena_height_m, y_m))
        self._set_pose_m(x_m, y_m, theta)

        trail_x, trail_y = self.robot_x, self.robot_y
        if not self._legacy_cm:
            trail_x, trail_y = x_m, y_m
        self.trail.append((trail_x, trail_y))
        if len(self.trail) > 2000:
            self.trail = self.trail[-1000:]

    def reset_pose(self, x: float, y: float, theta: float) -> None:
        self.robot_x = x
        self.robot_y = y
        self.robot_theta = theta
        self.trail = [(x, y)]

    def set_slip(self, esq: float, dir_: float) -> None:
        self.slip_esq = esq
        self.slip_dir = dir_

    def noisy_encoder(self, w: float) -> float:
        """Adiciona ruído ao encoder (se configurado)."""
        if self.encoder_noise_std > 0:
            return w + self._rng.gauss(0, self.encoder_noise_std)
        return w

    def noisy_gyro_z(self, omega_z_rads: float) -> float:
        """Adiciona drift ao giroscópio (se configurado)."""
        return omega_z_rads + self.gyro_drift_rads + self._rng.gauss(0, 0.01)

    def get_state(self) -> dict:
        """Retorna estado completo do mundo para a rota /demo."""
        return {
            "robot": {
                "x_m": round(self.robot_x, 4),
                "y_m": round(self.robot_y, 4),
                "theta_rad": round(self.robot_theta, 4),
                "theta_deg": round(math.degrees(self.robot_theta), 2),
            },
            "tags": [
                {
                    "position_id": t.position_id,
                    "x_m": round(t.x_m, 4),
                    "y_m": round(t.y_m, 4),
                    "yaw_deg": round(math.degrees(t.yaw_rad), 2),
                    "april_tag_id": t.april_tag_id,
                }
                for t in self.tags
            ],
            "arena": {
                "width_m": self.arena_width_m,
                "height_m": self.arena_height_m,
            },
            "trail": self.trail[-200:],
        }
