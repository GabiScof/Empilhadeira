"""Testes do GyroCalibrator (auto-orientação + bias na partida).

Cobre:
- Não calibra até atingir min_samples parado.
- Z para cima: taxa de yaw = gz (sinal +), bias subtraído.
- Z para baixo (placa invertida): sinal do yaw auto-invertido pela gravidade.
- Eixo de yaw auto-detectado quando a placa está deitada (gravidade em X).
- Bias na componente vertical é subtraído.
- Amostras em movimento (cmd OU encoder) não entram na calibração.
- Inclinação da placa é medida (tilt_deg).
- Modo manual (auto_orient=False) usa Z com sinal fixo.
- Drift térmico rastreado por EMA.
- reset() zera tudo.
"""

import math

import pytest

G = 9.81


def _make(min_samples=4, eps=0.05, alpha=0.1, auto=True, fixed_sign=1.0):
    from app.control.gyro_calibration import GyroCalibrator

    return GyroCalibrator(
        min_samples=min_samples,
        stationary_eps_rads=eps,
        track_alpha=alpha,
        auto_orient=auto,
        fixed_sign=fixed_sign,
    )


STILL = dict(w_left_cmd=0.0, w_right_cmd=0.0, w_left_meas=0.0, w_right_meas=0.0)
# Girando no lugo: NÃO parado → lê yaw sem disparar o rastreio de bias.
MOVING = dict(w_left_cmd=1.0, w_right_cmd=-1.0, w_left_meas=1.0, w_right_meas=-1.0)


def _feed(cal, gyro, accel, n, **wheels):
    out = None
    for _ in range(n):
        out = cal.update(gyro, accel, **{**STILL, **wheels})
    return out


class TestGyroCalibrator:
    def test_not_calibrated_before_min_samples(self):
        cal = _make(min_samples=5)
        _feed(cal, (0, 0, 0), (0, 0, G), 4)
        assert not cal.calibrated

    def test_z_up_positive_sign(self):
        cal = _make(min_samples=4)
        # gz=0 durante a calibração (parado), accel Z=+g → Z p/ cima.
        _feed(cal, (0.0, 0.0, 0.0), (0.0, 0.0, G), 4)
        assert cal.calibrated
        assert cal.axis_label == "+Z"
        assert cal.bias_dps == pytest.approx(0.0, abs=1e-9)
        # giro CCW (gz=+3) → yaw +3
        yaw = cal.update((0.0, 0.0, 3.0), (0.0, 0.0, G), **MOVING)
        assert yaw == pytest.approx(3.0)

    def test_z_down_auto_inverts_sign(self):
        cal = _make(min_samples=4)
        # placa invertida: accel Z = -g → +Z aponta p/ baixo.
        _feed(cal, (0.0, 0.0, 0.0), (0.0, 0.0, -G), 4)
        assert cal.calibrated
        assert cal.axis_label == "-Z"
        # mesma leitura crua gz=+3 agora vira yaw -3 (auto-invertido!)
        yaw = cal.update((0.0, 0.0, 3.0), (0.0, 0.0, -G), **MOVING)
        assert yaw == pytest.approx(-3.0)

    def test_detects_yaw_axis_when_board_on_side(self):
        # placa deitada: gravidade em +X → eixo de yaw = X.
        cal = _make(min_samples=4)
        _feed(cal, (0.0, 0.0, 0.0), (G, 0.0, 0.0), 4)
        assert cal.axis_label == "+X"
        # rotação sobre X (gx=+2) é o yaw
        yaw = cal.update((2.0, 0.0, 0.0), (G, 0.0, 0.0), **MOVING)
        assert yaw == pytest.approx(2.0)

    def test_bias_subtracted_on_vertical_axis(self):
        cal = _make(min_samples=4)
        # parado com gz=1.5 constante e Z p/ cima → bias=1.5
        _feed(cal, (0.0, 0.0, 1.5), (0.0, 0.0, G), 4)
        assert cal.bias_dps == pytest.approx(1.5)
        yaw = cal.update((0.0, 0.0, 1.5), (0.0, 0.0, G), **STILL)
        assert yaw == pytest.approx(0.0)

    def test_moving_samples_ignored(self):
        cal = _make(min_samples=4)
        moving = dict(w_left_cmd=1.0, w_right_cmd=1.0, w_left_meas=1.0, w_right_meas=1.0)
        _feed(cal, (0, 0, 9.9), (0, 0, G), 10, **moving)
        assert not cal.calibrated
        _feed(cal, (0.0, 0.0, 0.0), (0.0, 0.0, G), 4)
        assert cal.calibrated
        assert cal.bias_dps == pytest.approx(0.0, abs=1e-9)

    def test_measured_motion_blocks_calibration(self):
        cal = _make(min_samples=2)
        pushed = dict(w_left_cmd=0.0, w_right_cmd=0.0, w_left_meas=0.2, w_right_meas=0.0)
        _feed(cal, (0, 0, 5.0), (0, 0, G), 5, **pushed)
        assert not cal.calibrated

    def test_tilt_measured(self):
        cal = _make(min_samples=4)
        # 20° de inclinação: gravidade repartida entre X e Z.
        ax, az = G * math.sin(math.radians(20)), G * math.cos(math.radians(20))
        _feed(cal, (0.0, 0.0, 0.0), (ax, 0.0, az), 4)
        assert cal.axis_label == "+Z"  # Z ainda domina
        assert cal.tilt_deg == pytest.approx(20.0, abs=0.5)

    def test_manual_mode_fixed_sign(self):
        cal = _make(min_samples=2, auto=False, fixed_sign=-1.0)
        # accel irrelevante no modo manual; assume Z com sinal -1.
        _feed(cal, (0.0, 0.0, 0.0), (0.0, 0.0, G), 2)
        assert cal.axis_label == "-Z"
        yaw = cal.update((0.0, 0.0, 3.0), (0.0, 0.0, G), **MOVING)
        assert yaw == pytest.approx(-3.0)

    def test_thermal_drift_tracking(self):
        cal = _make(min_samples=2, alpha=0.5)
        _feed(cal, (0.0, 0.0, 0.0), (0.0, 0.0, G), 2)  # bias=0, Z up
        cal.update((0.0, 0.0, 4.0), (0.0, 0.0, G), **STILL)  # bias += 0.5*(4-0)=2
        assert cal.bias_dps == pytest.approx(2.0)

    def test_reset(self):
        cal = _make(min_samples=2)
        _feed(cal, (0.0, 0.0, 0.0), (0.0, 0.0, G), 2)
        assert cal.calibrated
        cal.reset()
        assert not cal.calibrated
        assert cal.bias_dps == 0.0
        assert cal.axis_label == "?"

    def test_dead_frames_do_not_poison_boot_calibration(self):
        """Frame morto do MPU (accel ~0, fisicamente impossível) é descartado.

        Assinaturas documentadas no readMpu do firmware (2026-07-06): I2C caiu
        (campos no default 0) ou sensor dormindo (14 bytes zero). Sem a guarda,
        frames mortos no boot entram na média da gravidade e o eixo vertical
        sai errado.
        """
        cal = _make(min_samples=4)
        # 3 frames mortos no meio do ritual de boot: não contam como amostra.
        _feed(cal, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 3)
        assert not cal.calibrated
        # 4 frames vivos calibram normalmente, com o eixo certo.
        _feed(cal, (0.0, 0.0, 0.0), (0.0, 0.0, G), 4)
        assert cal.calibrated
        assert cal.axis_label == "+Z"

    def test_dead_frames_do_not_erode_tracked_bias(self):
        cal = _make(min_samples=2, alpha=0.5)
        _feed(cal, (0.0, 0.0, 2.0), (0.0, 0.0, G), 2)  # bias travado em 2°/s
        assert cal.bias_dps == pytest.approx(2.0)
        # Frames mortos parado: sem a guarda, yaw_raw=0 puxaria o bias p/ 0.
        _feed(cal, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 10)
        assert cal.bias_dps == pytest.approx(2.0)
        # E a saída durante o frame morto é 0 (EKF segue só com encoders).
        assert cal.update((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), **STILL) == 0.0
