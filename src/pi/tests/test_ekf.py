"""Testes do EKF 2D [x, y, θ].

Cobre:
- Predição por odometria: robô avança em linha reta, pose muda.
- Predição por giro: robô gira no lugar, θ muda.
- Predição acumula drift sem correção.
- Correção por tag puxa a pose para o valor correto.
- Outlier rejeitado pelo gating de Mahalanobis.
- Covariância cresce com predição, diminui com correção.
- Reset zera tudo.
"""

import math

import numpy as np
import pytest


class TestPoseEKF:
    def _make_ekf(self, x=0.0, y=0.0, theta=0.0):
        from app.control.ekf import PoseEKF

        return PoseEKF(x, y, theta)

    def test_initial_state(self):
        ekf = self._make_ekf(1.0, 2.0, math.pi / 2)
        assert abs(ekf.x - 1.0) < 1e-6
        assert abs(ekf.y - 2.0) < 1e-6
        assert abs(ekf.theta - math.pi / 2) < 1e-6

    def test_predict_forward(self):
        ekf = self._make_ekf(0.0, 0.0, 0.0)  # apontando +X
        # Rodas iguais = avançar reto
        for _ in range(20):
            ekf.predict(5.0, 5.0, 0.0, 0.05, 0.028, 0.15)
        assert ekf.x > 0.1  # avançou em X
        assert abs(ekf.y) < 0.01  # não desviou em Y
        assert abs(ekf.theta) < 0.1  # theta ~= 0

    def test_predict_turn(self):
        ekf = self._make_ekf(0.0, 0.0, 0.0)
        # Rodas opostas = giro no lugar
        for _ in range(20):
            ekf.predict(-3.0, 3.0, math.radians(50), 0.05, 0.028, 0.15)
        assert abs(ekf.theta) > 0.3  # girou significativamente

    def test_drift_without_correction(self):
        ekf = self._make_ekf(0.0, 0.0, 0.0)
        cov_initial = ekf.covariance_trace
        for _ in range(100):
            ekf.predict(5.0, 5.0, 0.0, 0.05, 0.028, 0.15)
        assert ekf.covariance_trace > cov_initial

    def test_correction_pulls_pose(self):
        ekf = self._make_ekf(0.0, 0.0, 0.0)
        # Predição coloca em ~(0.07, 0, 0) após vários passos
        for _ in range(10):
            ekf.predict(5.0, 5.0, 0.0, 0.05, 0.028, 0.15)
        x_before, y_before = ekf.x, ekf.y
        # Observação moderada — dentro do gate de Mahalanobis
        obs_x, obs_y, obs_theta = 0.20, 0.10, 0.08
        applied = ekf.correct_apriltag(obs_x, obs_y, obs_theta, quality=1.0)
        assert applied
        # A pose deve ter se movido em direção à correção
        assert abs(ekf.x - obs_x) < abs(x_before - obs_x)
        assert abs(ekf.y - obs_y) < abs(y_before - obs_y)

    def test_outlier_rejected(self):
        ekf = self._make_ekf(0.0, 0.0, 0.0)
        # Covariância pequena → observação muito distante é rejeitada
        ekf._P = np.eye(3) * 0.0001  # covariância muito pequena
        applied = ekf.correct_apriltag(100.0, 100.0, math.pi, quality=1.0)
        assert not applied
        assert abs(ekf.x) < 0.01  # não se moveu

    def test_covariance_shrinks_with_correction(self):
        ekf = self._make_ekf(0.0, 0.0, 0.0)
        for _ in range(50):
            ekf.predict(5.0, 5.0, 0.0, 0.05, 0.028, 0.15)
        cov_before = ekf.covariance_trace
        ekf.correct_apriltag(ekf.x, ekf.y, ekf.theta, quality=1.0)
        assert ekf.covariance_trace < cov_before

    def test_reset(self):
        ekf = self._make_ekf(1.0, 2.0, 0.5)
        ekf.predict(5.0, 5.0, 0.0, 0.1, 0.028, 0.15)
        ekf.reset(0.0, 0.0, 0.0)
        assert abs(ekf.x) < 1e-6
        assert abs(ekf.y) < 1e-6
        assert abs(ekf.theta) < 1e-6

    def test_ellipse_params(self):
        ekf = self._make_ekf()
        major, minor, angle = ekf.get_ellipse_params()
        assert major >= 0
        assert minor >= 0
        assert major >= minor

    def test_to_dict(self):
        ekf = self._make_ekf(0.5, 0.3, math.pi / 4)
        d = ekf.to_dict()
        assert "x_m" in d
        assert "y_m" in d
        assert "theta_rad" in d
        assert "ellipse" in d
