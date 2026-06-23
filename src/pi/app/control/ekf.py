"""EKF de pose 2D — [x, y, θ] com fusão de odometria e AprilTag.

Substitui o AttitudeKalman (4 estados: roll, pitch, rates) por um filtro
de pose no plano que é o que a navegação precisa.

Matrizes do filtro (documentação em PT-BR):

**Estado:** x = [x, y, θ]  (m, m, rad)

**Predição (F):** modelo de cinemática diferencial.
  Dado (ω_esq, ω_dir) em rad/s e dt:
    v = r·(ω_esq + ω_dir)/2
    ω = r·(ω_dir − ω_esq)/L
    x' = x + v·cos(θ)·dt
    y' = y + v·sin(θ)·dt
    θ' = θ + ω·dt  (corrigido pelo giroscópio gz)

  Jacobiano F = ∂f/∂x:
    [[1, 0, −v·sin(θ)·dt],
     [0, 1,  v·cos(θ)·dt],
     [0, 0,  1           ]]

**Ruído de processo (Q):** diagonal, cresce com |v| e |ω| (odometria piora
com velocidade e giro). TODO(equipe): calibrar.

**Observação por AprilTag (H):**
  Quando uma tag de posição conhecida é detectada, usamos PnP para estimar
  a pose do robô no mundo. A observação é:
    z_obs = [x_tag − dx_cam, y_tag − dy_cam, θ_tag − dθ_cam]

  H = I(3×3) (observação direta do estado).

**Ruído de observação (R):** diagonal, depende da qualidade da detecção
(distância, resolução). TODO(equipe): calibrar.

**Gating (Mahalanobis):** rejeita correções com distância de Mahalanobis
acima de um limiar (default 3.0σ) para evitar que blur/detecções ruins
contaminem a pose.

[ref: Seção 3 do mega-prompt]
"""

from __future__ import annotations

import math
from enum import StrEnum

import numpy as np


class CorrectionSource(StrEnum):
    """Fonte da última correção aplicada ao EKF."""

    NONE = "none"
    ODOMETRY = "odometry"
    APRILTAG = "apriltag"
    RESET = "reset"


class PoseEKF:
    """EKF 2D para estimativa de pose [x, y, θ].

    Atributos públicos:
        state: np.ndarray de shape (3,) — [x, y, θ] em (m, m, rad).
        covariance: np.ndarray de shape (3, 3) — P.
        last_correction_source: CorrectionSource.
    """

    MAHALANOBIS_GATE: float = 3.0  # TODO(equipe): calibrar

    # Ruído de processo base (escala com velocidade)
    Q_BASE_XY: float = 0.001  # TODO(equipe): calibrar (m²)
    Q_BASE_THETA: float = 0.002  # TODO(equipe): calibrar (rad²)

    # Ruído de observação por AprilTag
    R_XY: float = 0.01  # TODO(equipe): calibrar (m²)
    R_THETA: float = 0.05  # TODO(equipe): calibrar (rad²)

    def __init__(self, x: float = 0.0, y: float = 0.0, theta: float = 0.0) -> None:
        self._x = np.array([x, y, theta], dtype=float)
        self._P = np.eye(3) * 0.01
        self._last_source = CorrectionSource.RESET
        self._correction_count = 0

    @property
    def state(self) -> np.ndarray:
        return self._x.copy()

    @property
    def x(self) -> float:
        return float(self._x[0])

    @property
    def y(self) -> float:
        return float(self._x[1])

    @property
    def theta(self) -> float:
        return float(self._x[2])

    @property
    def covariance(self) -> np.ndarray:
        return self._P.copy()

    @property
    def covariance_trace(self) -> float:
        return float(np.trace(self._P))

    @property
    def last_correction_source(self) -> CorrectionSource:
        return self._last_source

    @property
    def correction_count(self) -> int:
        return self._correction_count

    def predict(
        self,
        w_left: float,
        w_right: float,
        gyro_z_rads: float,
        dt: float,
        wheel_radius_m: float,
        wheelbase_m: float,
    ) -> None:
        """Predição por odometria + giroscópio.

        Args:
            w_left: velocidade angular roda esquerda (rad/s).
            w_right: velocidade angular roda direita (rad/s).
            gyro_z_rads: velocidade angular do giroscópio no eixo Z (rad/s).
            dt: intervalo de tempo (s).
            wheel_radius_m: raio da roda (m).
            wheelbase_m: distância entre rodas (m).
        """
        if dt <= 0:
            return

        r = wheel_radius_m
        L = wheelbase_m

        v = r * (w_left + w_right) / 2.0
        omega_odom = r * (w_right - w_left) / L

        # Fusão simples: média ponderada entre odometria e giroscópio para θ
        alpha_gyro = 0.7  # TODO(equipe): calibrar peso do giroscópio
        omega = alpha_gyro * gyro_z_rads + (1.0 - alpha_gyro) * omega_odom

        theta = self._x[2]

        # Predição do estado
        dx = v * math.cos(theta) * dt
        dy = v * math.sin(theta) * dt
        dtheta = omega * dt

        self._x[0] += dx
        self._x[1] += dy
        self._x[2] += dtheta
        self._x[2] = math.atan2(math.sin(self._x[2]), math.cos(self._x[2]))

        # Jacobiano F
        F = np.array([
            [1.0, 0.0, -v * math.sin(theta) * dt],
            [0.0, 1.0, v * math.cos(theta) * dt],
            [0.0, 0.0, 1.0],
        ])

        # Ruído de processo proporcional à velocidade
        speed_factor = max(abs(v), 0.01)
        turn_factor = max(abs(omega), 0.01)
        Q = np.diag([
            self.Q_BASE_XY * speed_factor,
            self.Q_BASE_XY * speed_factor,
            self.Q_BASE_THETA * turn_factor,
        ]) * dt

        self._P = F @ self._P @ F.T + Q
        self._last_source = CorrectionSource.ODOMETRY

    def correct_apriltag(
        self,
        observed_x: float,
        observed_y: float,
        observed_theta: float,
        quality: float = 1.0,
    ) -> bool:
        """Correção por AprilTag: fix absoluto de pose.

        A posição observada já deve estar no frame do mundo (convertida a
        partir da posição conhecida da tag e da pose relativa câmera-tag).

        Args:
            observed_x: posição X observada no mundo (m).
            observed_y: posição Y observada no mundo (m).
            observed_theta: orientação observada no mundo (rad).
            quality: fator de qualidade [0, 1] — 1.0 = detecção perfeita.

        Returns:
            True se a correção foi aplicada; False se rejeitada pelo gating.
        """
        z = np.array([observed_x, observed_y, observed_theta])
        h_x = self._x.copy()  # H = I → h(x) = x

        innovation = z - h_x
        innovation[2] = math.atan2(math.sin(innovation[2]), math.cos(innovation[2]))

        H = np.eye(3)

        quality_scale = max(quality, 0.1)
        R = np.diag([
            self.R_XY / quality_scale,
            self.R_XY / quality_scale,
            self.R_THETA / quality_scale,
        ])

        S = H @ self._P @ H.T + R

        # Gating de Mahalanobis
        try:
            S_inv = np.linalg.inv(S)
        except np.linalg.LinAlgError:
            return False

        mahal = float(innovation.T @ S_inv @ innovation)
        mahal_dist = math.sqrt(max(mahal, 0.0))

        if mahal_dist > self.MAHALANOBIS_GATE:
            return False

        K = self._P @ H.T @ S_inv

        self._x += K @ innovation
        self._x[2] = math.atan2(math.sin(self._x[2]), math.cos(self._x[2]))

        I_KH = np.eye(3) - K @ H
        self._P = I_KH @ self._P @ I_KH.T + K @ R @ K.T

        self._last_source = CorrectionSource.APRILTAG
        self._correction_count += 1
        return True

    def reset(self, x: float, y: float, theta: float) -> None:
        """Reseta a pose e a covariância."""
        self._x = np.array([x, y, theta], dtype=float)
        self._P = np.eye(3) * 0.01
        self._last_source = CorrectionSource.RESET
        self._correction_count = 0

    def get_ellipse_params(self) -> tuple[float, float, float]:
        """Retorna parâmetros da elipse de covariância 2D (x, y) para a UI.

        Returns:
            (semi_major_m, semi_minor_m, angle_rad) — eixos e ângulo da elipse.
        """
        P_xy = self._P[:2, :2]
        eigenvalues, eigenvectors = np.linalg.eigh(P_xy)
        eigenvalues = np.maximum(eigenvalues, 0.0)

        order = eigenvalues.argsort()[::-1]
        eigenvalues = eigenvalues[order]
        eigenvectors = eigenvectors[:, order]

        chi2_95 = 5.991  # 95% confidence for 2 DOF
        semi_major = math.sqrt(eigenvalues[0] * chi2_95)
        semi_minor = math.sqrt(eigenvalues[1] * chi2_95)
        angle = math.atan2(eigenvectors[1, 0], eigenvectors[0, 0])

        return semi_major, semi_minor, angle

    def to_dict(self) -> dict:
        """Serializa para telemetria."""
        semi_major, semi_minor, angle = self.get_ellipse_params()
        return {
            "x_m": round(self.x, 4),
            "y_m": round(self.y, 4),
            "theta_rad": round(self.theta, 4),
            "theta_deg": round(math.degrees(self.theta), 2),
            "covariance_trace": round(self.covariance_trace, 6),
            "last_correction": self._last_source.value,
            "correction_count": self._correction_count,
            "ellipse": {
                "semi_major_m": round(semi_major, 4),
                "semi_minor_m": round(semi_minor, 4),
                "angle_rad": round(angle, 4),
            },
        }
