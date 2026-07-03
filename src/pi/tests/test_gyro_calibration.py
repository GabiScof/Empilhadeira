"""Testes do GyroCalibrator (bias de taxa-zero do giroscópio).

Cobre:
- Não calibra até atingir min_samples parado.
- Trava o bias como a média das amostras paradas e o subtrai.
- Amostras com o robô em movimento não entram na estimativa.
- Movimento (cmd OU encoder acima de eps) conta como não-parado.
- Sinal inverte a taxa de saída.
- Drift térmico é rastreado por EMA após calibrado.
- reset() zera tudo.
"""

import pytest


def _make(min_samples=4, eps=0.05, alpha=0.1, sign=1.0):
    from app.control.gyro_calibration import GyroCalibrator

    return GyroCalibrator(
        min_samples=min_samples,
        stationary_eps_rads=eps,
        track_alpha=alpha,
        sign=sign,
    )


STILL = dict(w_left_cmd=0.0, w_right_cmd=0.0, w_left_meas=0.0, w_right_meas=0.0)


class TestGyroCalibrator:
    def test_not_calibrated_before_min_samples(self):
        cal = _make(min_samples=5)
        for _ in range(3):
            cal.update(2.0, **STILL)
        assert not cal.calibrated
        # Antes de calibrar (4ª amostra, ainda < 5), bias=0 → saída é o cru.
        assert cal.update(2.0, **STILL) == pytest.approx(2.0)
        assert not cal.calibrated

    def test_locks_bias_as_mean(self):
        cal = _make(min_samples=4)
        for v in (1.0, 2.0, 3.0, 4.0):  # média = 2.5
            out = cal.update(v, **STILL)
        assert cal.calibrated
        assert cal.bias_dps == pytest.approx(2.5)
        # última amostra (4.0) já sai corrigida: 4.0 - 2.5 = 1.5
        assert out == pytest.approx(1.5)
        # leitura crua igual ao bias → yaw ~0
        assert cal.update(2.5, **STILL) == pytest.approx(0.0)

    def test_moving_samples_ignored(self):
        cal = _make(min_samples=4)
        moving = dict(w_left_cmd=1.0, w_right_cmd=1.0, w_left_meas=1.0, w_right_meas=1.0)
        for _ in range(10):
            cal.update(9.9, **moving)  # não deve acumular
        assert not cal.calibrated
        for v in (1.0, 1.0, 1.0, 1.0):
            cal.update(v, **STILL)
        assert cal.calibrated
        assert cal.bias_dps == pytest.approx(1.0)

    def test_measured_motion_blocks_calibration(self):
        cal = _make(min_samples=2, eps=0.05)
        # comando zero mas encoder acima de eps (robô empurrado / inércia)
        pushed = dict(w_left_cmd=0.0, w_right_cmd=0.0, w_left_meas=0.2, w_right_meas=0.0)
        cal.update(5.0, **pushed)
        cal.update(5.0, **pushed)
        assert not cal.calibrated

    def test_sign_inverts_output(self):
        # alpha=0 desliga o rastreio p/ isolar o efeito do sinal.
        cal = _make(min_samples=2, sign=-1.0, alpha=0.0)
        cal.update(0.0, **STILL)
        cal.update(0.0, **STILL)  # bias=0, calibrado
        assert cal.update(3.0, **STILL) == pytest.approx(-3.0)

    def test_thermal_drift_tracking(self):
        cal = _make(min_samples=2, alpha=0.5)
        cal.update(0.0, **STILL)
        cal.update(0.0, **STILL)  # bias=0
        # parado mas lendo 4.0 → EMA puxa o bias na direção de 4.0
        cal.update(4.0, **STILL)  # bias += 0.5*(4-0) = 2.0
        assert cal.bias_dps == pytest.approx(2.0)

    def test_reset(self):
        cal = _make(min_samples=2)
        cal.update(3.0, **STILL)
        cal.update(3.0, **STILL)
        assert cal.calibrated
        cal.reset()
        assert not cal.calibrated
        assert cal.bias_dps == 0.0
