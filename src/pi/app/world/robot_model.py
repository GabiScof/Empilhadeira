"""Modelo geométrico do robô — independente da arena.

Centraliza as dimensões físicas do robô (base entre rodas, raio da roda,
resolução do encoder) usadas pela cinemática, EKF e simulador.

Todos os valores em SI (metros, radianos). Valores provisórios marcados com
TODO(equipe).

"""

from __future__ import annotations

import math


class RobotModel:
    """Geometria e parâmetros cinemáticos do robô.

    Atributos:
        wheelbase_m: distância entre rodas (m).
        wheel_radius_m: raio da roda (m).
        encoder_ppr: pulsos por revolução do encoder (com redução).
        max_linear_speed_ms: velocidade linear máxima (m/s).
        max_angular_speed_rads: velocidade angular máxima (rad/s).
    """

    def __init__(
        self,
        wheelbase_m: float = 0.15,      # TODO(equipe): confirmar (quadro: L ≈ 15 cm)
        wheel_radius_m: float = 0.028,  # TODO(equipe): medir raio da roda NXT (~56 mm diâmetro)
        encoder_ppr: int = 360,          # TODO(equipe): confirmar pulsos/rev com redução
        max_linear_speed_ms: float = 0.30,  # TODO(equipe): confirmar
        max_angular_speed_rads: float = 3.0,  # TODO(equipe): confirmar
    ) -> None:
        self.wheelbase_m = wheelbase_m
        self.wheel_radius_m = wheel_radius_m
        self.encoder_ppr = encoder_ppr
        self.max_linear_speed_ms = max_linear_speed_ms
        self.max_angular_speed_rads = max_angular_speed_rads

    @property
    def half_wheelbase_m(self) -> float:
        return self.wheelbase_m / 2.0

    def rad_per_pulse(self) -> float:
        """Radianos por pulso do encoder."""
        return (2.0 * math.pi) / self.encoder_ppr

    def forward_kinematics(
        self, w_left: float, w_right: float
    ) -> tuple[float, float]:
        """Cinemática direta: (ω_esq, ω_dir) → (v, ω).

        Args:
            w_left: velocidade angular roda esquerda (rad/s).
            w_right: velocidade angular roda direita (rad/s).

        Returns:
            (v_ms, omega_rads) — velocidade linear (m/s) e angular (rad/s).
        """
        r = self.wheel_radius_m
        v = r * (w_left + w_right) / 2.0
        omega = r * (w_right - w_left) / self.wheelbase_m
        return v, omega

    def inverse_kinematics(
        self, v: float, omega: float
    ) -> tuple[float, float]:
        """Cinemática inversa: (v, ω) → (ω_esq, ω_dir).

        Args:
            v: velocidade linear (m/s).
            omega: velocidade angular (rad/s).

        Returns:
            (w_left, w_right) em rad/s.
        """
        r = self.wheel_radius_m
        half_l = self.half_wheelbase_m
        w_left = (v - omega * half_l) / r
        w_right = (v + omega * half_l) / r
        return w_left, w_right

    def diff_drive_step(
        self,
        x: float, y: float, theta: float,
        w_left: float, w_right: float,
        dt: float,
    ) -> tuple[float, float, float]:
        """Integra cinemática diferencial por dt segundos.

        Args:
            x, y: posição atual (m).
            theta: orientação atual (rad).
            w_left, w_right: velocidades angulares das rodas (rad/s).
            dt: intervalo de tempo (s).

        Returns:
            (x_new, y_new, theta_new) — nova pose.
        """
        v, omega = self.forward_kinematics(w_left, w_right)

        if abs(omega) < 1e-8:
            x_new = x + v * math.cos(theta) * dt
            y_new = y + v * math.sin(theta) * dt
            theta_new = theta
        else:
            radius = v / omega
            theta_new = theta + omega * dt
            x_new = x + radius * (math.sin(theta_new) - math.sin(theta))
            y_new = y - radius * (math.cos(theta_new) - math.cos(theta))

        theta_new = math.atan2(math.sin(theta_new), math.cos(theta_new))
        return x_new, y_new, theta_new
