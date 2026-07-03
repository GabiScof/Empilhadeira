"""Testes da navegação automática: APPROACH/FACE/RETREAT, dead zone com D."""

import math

from app import config
from app.control.navigation import (
    _ALPHA_MIN,
    _BEARING_KP,
    _CENTER_THRESH,
    _CONVERGE_D_TOL,
    _CONVERGE_P_TOL,
    _CONVERGE_Z_TOL,
    _FACE_MIN_TICKS,
    _FACE_TRIGGER_D,
    _FACE_TRIGGER_TICKS,
    _FACE_X_ALIGNED,
    _RETREAT_TARGET_Z,
    _true_lateral,
    NavigationController,
    compute_twist_fallback,
    compute_twist_primary,
)


def test_primary_converges_z():
    v, omega = compute_twist_primary(z_cm=30.0, x_cm=0.0, pitch_deg=0.0)
    assert v > 0


def test_primary_stops_at_zref():
    v, omega = compute_twist_primary(z_cm=config.ZREF_CM, x_cm=0.0, pitch_deg=0.0)
    assert abs(v) < 0.1


def test_primary_far_uses_xcm():
    v1, omega1 = compute_twist_primary(z_cm=80.0, x_cm=0.0, pitch_deg=0.0)
    v2, omega2 = compute_twist_primary(z_cm=80.0, x_cm=-10.0, pitch_deg=0.0)
    assert omega2 < omega1


def test_centering_mode_uses_bearing():
    x = _CENTER_THRESH + 1.0
    z = 30.0
    v, omega = compute_twist_primary(z_cm=z, x_cm=x, pitch_deg=0.0)
    bearing_deg = math.degrees(math.atan2(x, z))
    expected = _BEARING_KP * bearing_deg
    assert abs(omega - expected) < 0.1


def test_bearing_scales_with_distance():
    """Same x offset at different z should give different omega."""
    _, omega_far = compute_twist_primary(z_cm=100.0, x_cm=10.0, pitch_deg=0.0)
    _, omega_near = compute_twist_primary(z_cm=20.0, x_cm=10.0, pitch_deg=0.0)
    assert abs(omega_near) > abs(omega_far)


def test_alignment_mode_when_centered():
    x = 0.5
    pitch = 4.0
    v, omega = compute_twist_primary(
        z_cm=config.ZREF_CM + 3.0, x_cm=x, pitch_deg=pitch
    )
    expected = config.NAV_KP_PITCH * pitch + _ALPHA_MIN * config.NAV_KX * x
    assert abs(omega - expected) < 0.05


def test_centering_slows_v():
    v_center, _ = compute_twist_primary(z_cm=30.0, x_cm=0.0, pitch_deg=0.0)
    v_offset, _ = compute_twist_primary(z_cm=30.0, x_cm=5.0, pitch_deg=0.0)
    assert v_offset < v_center


def test_dead_zone_uses_d():
    z = config.ZREF_CM + 0.5
    v, omega = compute_twist_primary(z_cm=z, x_cm=0.5, pitch_deg=1.0)
    assert v == 0.0 and omega == 0.0


def test_dead_zone_rejects_large_d():
    z = config.ZREF_CM + 0.5
    v, omega = compute_twist_primary(z_cm=z, x_cm=0.5, pitch_deg=15.0)
    assert not (v == 0.0 and omega == 0.0)


def test_dead_zone_rejects_large_pitch():
    z = config.ZREF_CM + 0.5
    v, omega = compute_twist_primary(z_cm=z, x_cm=0.0, pitch_deg=8.0)
    assert not (v == 0.0 and omega == 0.0)


def test_true_lateral_zero_pitch():
    d = _true_lateral(x_cm=3.0, z_cm=20.0, pitch_deg=0.0)
    assert abs(d - 3.0) < 0.01


def test_true_lateral_caps_z():
    d1 = _true_lateral(x_cm=0.0, z_cm=100.0, pitch_deg=10.0)
    d2 = _true_lateral(x_cm=0.0, z_cm=config.ZREF_CM, pitch_deg=10.0)
    assert abs(d1 - d2) < 0.01


def test_heading_guard_suppresses_v():
    v, omega = compute_twist_primary(z_cm=20.0, x_cm=0.0, pitch_deg=35.0)
    assert v == 0.0
    assert abs(omega) > 0


def test_bearing_guard_reduces_v():
    v_center, _ = compute_twist_primary(z_cm=30.0, x_cm=0.0, pitch_deg=0.0)
    v_edge, _ = compute_twist_primary(z_cm=30.0, x_cm=15.0, pitch_deg=0.0)
    assert v_edge < v_center


def test_fallback_retreats_when_stuck():
    v, omega = compute_twist_fallback(z_cm=config.ZREF_CM, x_cm=0.0, pitch_deg=10.0)
    assert v < 0
    assert omega != 0


def test_fallback_approaches_far():
    v, omega = compute_twist_fallback(z_cm=30.0, x_cm=0.0, pitch_deg=0.0)
    assert v > 0


def _trigger_face(ctrl):
    """Helper: drive controller into FACE phase."""
    z = config.ZREF_CM + 1.0
    for _ in range(_FACE_TRIGGER_TICKS + 5):
        ctrl.compute(z_cm=z, x_cm=0.0, pitch_deg=-15.0)
    assert ctrl.phase == "FACE"


def _wait_face_min(ctrl):
    """Helper: keep in FACE for minimum duration with large pitch."""
    z = config.ZREF_CM + 1.0
    for _ in range(_FACE_MIN_TICKS):
        ctrl.compute(z_cm=z, x_cm=0.0, pitch_deg=-10.0)


def test_controller_face_trigger():
    ctrl = NavigationController()
    _trigger_face(ctrl)


def test_controller_face_respects_min_ticks():
    ctrl = NavigationController()
    _trigger_face(ctrl)
    z = config.ZREF_CM + 1.0
    ctrl.compute(z_cm=z, x_cm=5.0, pitch_deg=1.0)
    assert ctrl.phase == "FACE"


def test_controller_face_to_retreat():
    ctrl = NavigationController()
    _trigger_face(ctrl)
    _wait_face_min(ctrl)
    z = config.ZREF_CM + 1.0
    ctrl.compute(z_cm=z, x_cm=5.0, pitch_deg=1.0)
    assert ctrl.phase == "RETREAT"


def test_controller_face_to_approach_when_aligned():
    ctrl = NavigationController()
    _trigger_face(ctrl)
    _wait_face_min(ctrl)
    z = config.ZREF_CM + 1.0
    ctrl.compute(z_cm=z, x_cm=0.5, pitch_deg=1.0)
    assert ctrl.phase == "APPROACH"


def test_controller_retreat_exits():
    ctrl = NavigationController()
    _trigger_face(ctrl)
    _wait_face_min(ctrl)
    z = config.ZREF_CM + 1.0
    ctrl.compute(z_cm=z, x_cm=5.0, pitch_deg=1.0)
    assert ctrl.phase == "RETREAT"
    ctrl.compute(z_cm=_RETREAT_TARGET_Z + 1.0, x_cm=5.0, pitch_deg=0.0)
    assert ctrl.phase == "APPROACH"


def test_controller_uses_fallback_near_z():
    ctrl = NavigationController()
    z_near = config.NAV_MIN_Z_FOR_PRIMARY - 1
    ctrl.compute(z_cm=z_near, x_cm=0.0, pitch_deg=0.0)
    assert ctrl.using_fallback


def test_controller_uses_primary_far():
    ctrl = NavigationController()
    ctrl.compute(z_cm=50.0, x_cm=0.0, pitch_deg=0.0)
    assert not ctrl.using_fallback


def test_controller_reset():
    ctrl = NavigationController()
    ctrl.compute(z_cm=50.0, x_cm=5.0, pitch_deg=0.0)
    ctrl.reset()
    assert not ctrl.using_fallback
    assert ctrl.phase == "APPROACH"
    assert len(ctrl._omega_history) == 0


def test_omega_smoothing():
    """Omega should be smoothed across ticks, not jumping."""
    ctrl = NavigationController()
    ctrl.compute(z_cm=50.0, x_cm=10.0, pitch_deg=0.0)
    omega1 = ctrl._prev_omega
    ctrl.compute(z_cm=50.0, x_cm=-10.0, pitch_deg=0.0)
    omega2 = ctrl._prev_omega
    assert abs(omega2) < abs(omega1) or omega1 * omega2 > 0
