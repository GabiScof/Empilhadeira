"""Testes do filtro de Kalman: IMU ruidosa + drift → roll/pitch estáveis."""

import math
import random

from app.control.kalman import AttitudeKalman
from app.models import MpuRaw


def _static_mpu(noise_std: float = 0.0, rng: random.Random | None = None) -> MpuRaw:
    """MPU em repouso: az ≈ 9.81, outros ≈ 0 + ruído."""
    r = rng or random.Random(42)
    return MpuRaw(
        ax=r.gauss(0, noise_std),
        ay=r.gauss(0, noise_std),
        az=9.81 + r.gauss(0, noise_std),
        gx=r.gauss(0, noise_std * 0.1),
        gy=r.gauss(0, noise_std * 0.1),
        gz=r.gauss(0, noise_std * 0.1),
        temp_c=25.0,
    )


def test_kalman_initial_from_accel():
    """Primeira leitura inicializa a partir do acelerômetro."""
    kf = AttitudeKalman()
    mpu = MpuRaw(ax=0, ay=0, az=9.81, gx=0, gy=0, gz=0, temp_c=25)
    imu = kf.update(mpu, 0.05)
    assert abs(imu.roll) < 5
    assert abs(imu.pitch) < 5


def test_kalman_stable_static():
    """Com IMU estática (sem ruído), roll/pitch devem ficar próximos de zero."""
    kf = AttitudeKalman()
    dt = 0.05

    for _ in range(100):
        mpu = MpuRaw(ax=0, ay=0, az=9.81, gx=0, gy=0, gz=0, temp_c=25)
        imu = kf.update(mpu, dt)

    assert abs(imu.roll) < 1.0
    assert abs(imu.pitch) < 1.0


def test_kalman_noisy_converges():
    """Com ruído moderado, o filtro deve convergir para valores estáveis."""
    kf = AttitudeKalman()
    dt = 0.05
    rng = random.Random(42)

    rolls = []
    pitches = []
    for _ in range(200):
        mpu = _static_mpu(noise_std=0.5, rng=rng)
        imu = kf.update(mpu, dt)
        rolls.append(imu.roll)
        pitches.append(imu.pitch)

    last_20_rolls = rolls[-20:]
    last_20_pitches = pitches[-20:]
    roll_range = max(last_20_rolls) - min(last_20_rolls)
    pitch_range = max(last_20_pitches) - min(last_20_pitches)

    assert roll_range < 5.0
    assert pitch_range < 5.0


def test_kalman_filters_noise():
    """Saída filtrada deve ter variância menor que o acelerômetro cru."""
    kf = AttitudeKalman()
    dt = 0.05
    rng = random.Random(42)

    raw_pitches = []
    filtered_pitches = []

    for _ in range(200):
        mpu = _static_mpu(noise_std=1.0, rng=rng)
        raw_pitch = math.degrees(math.atan2(-mpu.ax, math.sqrt(mpu.ay**2 + mpu.az**2)))
        raw_pitches.append(raw_pitch)

        imu = kf.update(mpu, dt)
        filtered_pitches.append(imu.pitch)

    raw_mean = sum(raw_pitches) / len(raw_pitches)
    filt_mean = sum(filtered_pitches) / len(filtered_pitches)
    raw_var = sum((p - raw_mean) ** 2 for p in raw_pitches) / len(raw_pitches)
    filt_var = sum((p - filt_mean) ** 2 for p in filtered_pitches) / len(filtered_pitches)

    assert filt_var < raw_var


def test_kalman_reset():
    """reset() deve restaurar ao estado inicial."""
    kf = AttitudeKalman()
    mpu = MpuRaw(ax=0, ay=0, az=9.81, gx=0, gy=0, gz=0, temp_c=25)
    kf.update(mpu, 0.05)
    kf.reset()
    imu = kf.update(mpu, 0.05)
    assert abs(imu.roll) < 5
    assert abs(imu.pitch) < 5
