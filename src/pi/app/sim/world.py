"""Mundo de simulação: almoxarifado, pose do robô e do pallet/tag.

Integra a cinemática diferencial a partir das velocidades das rodas para atualizar
a pose do robô. O pallet/tag tem pose fixa (configurável). Suporta slip de roda
opcional e pose inicial arbitrária.

[ref: Seção 7 do mega-prompt]
"""

from __future__ import annotations

import math
import random

from app import config


class SimWorld:
    """Mundo retangular com robô e pallet."""

    def __init__(
        self,
        robot_x: float = 100.0,
        robot_y: float = 100.0,
        robot_theta: float = 0.0,
        tag_x: float = 100.0,
        tag_y: float = 50.0,
        tag_theta: float = math.pi,
        tag_id: int = 0,
        seed: int = config.SIM_DEFAULT_SEED,
    ) -> None:
        self.robot_x = robot_x
        self.robot_y = robot_y
        self.robot_theta = robot_theta

        self.tag_x = tag_x
        self.tag_y = tag_y
        self.tag_theta = tag_theta
        self.tag_id = tag_id

        self.arena_width = config.SIM_ARENA_WIDTH
        self.arena_height = config.SIM_ARENA_HEIGHT

        self._rng = random.Random(seed)

        self.slip_esq: float = 1.0
        self.slip_dir: float = 1.0

        self.trail: list[tuple[float, float]] = [(robot_x, robot_y)]

    def step(self, w_esq: float, w_dir: float, dt: float) -> None:
        """Integra a cinemática diferencial por dt segundos.

        Args:
            w_esq: velocidade angular roda esquerda (rad/s).
            w_dir: velocidade angular roda direita (rad/s).
            dt: intervalo de tempo (s).
        """
        w_esq_eff = w_esq * self.slip_esq
        w_dir_eff = w_dir * self.slip_dir

        r = config.WHEEL_RADIUS_R_CM
        L = config.WHEEL_BASE_L_CM

        v_esq = w_esq_eff * r
        v_dir = w_dir_eff * r

        v = (v_esq + v_dir) / 2.0
        omega = (v_dir - v_esq) / L

        if abs(omega) < 1e-6:
            self.robot_x += v * math.cos(self.robot_theta) * dt
            self.robot_y += v * math.sin(self.robot_theta) * dt
        else:
            radius = v / omega
            new_theta = self.robot_theta + omega * dt
            self.robot_x += radius * (math.sin(new_theta) - math.sin(self.robot_theta))
            self.robot_y -= radius * (math.cos(new_theta) - math.cos(self.robot_theta))
            self.robot_theta += omega * dt

        self.robot_theta = math.atan2(math.sin(self.robot_theta), math.cos(self.robot_theta))

        self.robot_x = max(0, min(self.arena_width, self.robot_x))
        self.robot_y = max(0, min(self.arena_height, self.robot_y))

        self.trail.append((self.robot_x, self.robot_y))
        if len(self.trail) > 2000:
            self.trail = self.trail[-1000:]

    def reset_pose(self, x: float, y: float, theta: float) -> None:
        """Define pose inicial arbitrária do robô."""
        self.robot_x = x
        self.robot_y = y
        self.robot_theta = theta
        self.trail = [(x, y)]

    def set_slip(self, esq: float, dir_: float) -> None:
        """Define multiplicadores de slip por roda (1.0 = sem slip)."""
        self.slip_esq = esq
        self.slip_dir = dir_

    def get_state(self) -> dict:
        """Retorna estado completo do mundo para a rota /demo."""
        return {
            "robot": {
                "x": round(self.robot_x, 2),
                "y": round(self.robot_y, 2),
                "theta": round(self.robot_theta, 4),
            },
            "tag": {
                "x": round(self.tag_x, 2),
                "y": round(self.tag_y, 2),
                "theta": round(self.tag_theta, 4),
                "id": self.tag_id,
            },
            "arena": {
                "width": self.arena_width,
                "height": self.arena_height,
            },
            "trail": self.trail[-200:],
        }
