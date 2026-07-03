"""Filtro de Kalman para fusão IMU: acelerômetro + giroscópio → roll/pitch estáveis.

O acelerômetro mede a gravidade (ruidoso, sem drift) e o giroscópio mede a
velocidade angular (suave, com drift). A fusão produz roll/pitch estáveis em graus.

Usa `filterpy.kalman.KalmanFilter` com estado [roll, pitch, roll_rate, pitch_rate].

[ref: Seção 7 da AGENTS.md]
"""

from __future__ import annotations

import math

import numpy as np
from filterpy.kalman import KalmanFilter

from app.models import ImuAngles, MpuRaw


class AttitudeKalman:
    """Filtro de Kalman para estimativa de roll/pitch a partir do MPU-6050."""

    def __init__(self) -> None:
        self._kf = KalmanFilter(dim_x=4, dim_z=2)

        # x = [roll, pitch, roll_rate, pitch_rate]
        self._kf.x = np.zeros(4)

        # Matriz de transição (atualizada a cada step com dt)
        self._kf.F = np.eye(4)

        # Matriz de observação: medimos roll e pitch do acelerômetro
        self._kf.H = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
            ]
        )

        # Covariância do processo (giroscópio, confiável no curto prazo)
        self._kf.Q = np.diag([0.001, 0.001, 0.003, 0.003])

        # Covariância da medição (acelerômetro, ruidoso)
        self._kf.R = np.diag([0.5, 0.5])

        # Covariância inicial
        self._kf.P *= 1.0

        self._initialized = False

    def update(self, mpu: MpuRaw, dt: float) -> ImuAngles:
        """Atualiza o filtro com uma nova leitura do MPU-6050.

        Args:
            mpu: leituras cruas do MPU-6050 (accel em m/s², gyro em graus/s).
            dt: intervalo desde a última chamada (segundos).

        Returns:
            ImuAngles com roll/pitch filtrados em graus.
        """
        if dt <= 0:
            return ImuAngles(roll=float(self._kf.x[0]), pitch=float(self._kf.x[1]))

        accel_roll = math.degrees(math.atan2(mpu.ay, mpu.az))
        accel_pitch = math.degrees(math.atan2(-mpu.ax, math.sqrt(mpu.ay**2 + mpu.az**2)))

        if not self._initialized:
            self._kf.x[0] = accel_roll
            self._kf.x[1] = accel_pitch
            self._kf.x[2] = mpu.gx
            self._kf.x[3] = mpu.gy
            self._initialized = True
            return ImuAngles(roll=accel_roll, pitch=accel_pitch)

        self._kf.F = np.array(
            [
                [1.0, 0.0, dt, 0.0],
                [0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )

        self._kf.B = np.array(
            [
                [dt, 0.0],
                [0.0, dt],
                [1.0, 0.0],
                [0.0, 1.0],
            ]
        )

        u = np.array([mpu.gx, mpu.gy])

        self._kf.predict(u=u)
        self._kf.update(np.array([accel_roll, accel_pitch]))

        return ImuAngles(
            roll=float(self._kf.x[0]),
            pitch=float(self._kf.x[1]),
        )

    def reset(self) -> None:
        """Reseta o filtro ao estado inicial."""
        self._kf.x = np.zeros(4)
        self._kf.P = np.eye(4)
        self._initialized = False
