"""Testes da navegação automática: convergência, fallback, FOV."""

from app import config
from app.control.navigation import (
    NavigationController,
    compute_twist_fallback,
    compute_twist_primary,
)


def test_primary_converges_z():
    """Estratégia A: com Z > Zref, v deve ser positivo (aproximando)."""
    v, omega = compute_twist_primary(z_cm=30.0, x_cm=0.0, pitch_deg=0.0)
    assert v > 0  # avançando para se aproximar


def test_primary_stops_at_zref():
    """Estratégia A: com Z ≈ Zref e X=0, Pitch=0, v ≈ 0."""
    v, omega = compute_twist_primary(z_cm=config.ZREF_CM, x_cm=0.0, pitch_deg=0.0)
    assert abs(v) < 0.1


def test_primary_corrects_x():
    """Estratégia A: com X != 0, omega deve corrigir lateralmente."""
    v, omega = compute_twist_primary(z_cm=20.0, x_cm=5.0, pitch_deg=0.0)
    assert omega != 0


def test_primary_corrects_pitch():
    """Estratégia A: com Pitch != 0, omega inclui correção."""
    v1, omega1 = compute_twist_primary(z_cm=20.0, x_cm=0.0, pitch_deg=0.0)
    v2, omega2 = compute_twist_primary(z_cm=20.0, x_cm=0.0, pitch_deg=10.0)
    assert abs(omega2) > abs(omega1)


def test_fallback_aligns_first():
    """Estratégia B: com X grande, corrige X antes de avançar."""
    v, omega = compute_twist_fallback(z_cm=30.0, x_cm=5.0, pitch_deg=10.0)
    assert abs(v) < 0.01
    assert omega != 0


def test_fallback_approaches_after_align():
    """Estratégia B: com X≈0 e Z longe, avança."""
    v, omega = compute_twist_fallback(z_cm=30.0, x_cm=0.0, pitch_deg=0.0)
    assert v > 0


def test_fallback_fine_tunes_pitch():
    """Estratégia B: com X≈0, Z≈Zref e Pitch grande, corrige pitch."""
    v, omega = compute_twist_fallback(z_cm=config.ZREF_CM, x_cm=0.0, pitch_deg=10.0)
    assert abs(v) < 0.01
    assert omega != 0


def test_controller_uses_fallback_near_z():
    """NavigationController usa fallback quando Z < limiar."""
    ctrl = NavigationController()
    z_near = config.NAV_MIN_Z_FOR_PRIMARY - 1
    v, omega = ctrl.compute(z_cm=z_near, x_cm=0.0, pitch_deg=0.0)
    assert ctrl.using_fallback


def test_controller_uses_primary_far():
    """NavigationController usa primária quando Z é grande."""
    ctrl = NavigationController()
    v, omega = ctrl.compute(z_cm=50.0, x_cm=0.0, pitch_deg=0.0)
    assert not ctrl.using_fallback


def test_controller_reset():
    """NavigationController.reset() limpa estado."""
    ctrl = NavigationController()
    ctrl.compute(z_cm=50.0, x_cm=5.0, pitch_deg=0.0)
    ctrl.reset()
    assert not ctrl.using_fallback
    assert len(ctrl._omega_history) == 0
