"""Testes da cinemática diferencial: avanço puro, giro, saturação, unidades."""

from app import config
from app.control.kinematics import (
    joystick_to_twist,
    twist_to_wheel_speeds,
    wheel_speeds_to_twist,
)


def test_straight_equal_wheels():
    """Avanço puro (ω=0) deve dar w_esq == w_dir."""
    v = 10.0  # cm/s
    omega = 0.0
    w_esq, w_dir = twist_to_wheel_speeds(v, omega)
    assert abs(w_esq - w_dir) < 1e-6


def test_pure_rotation():
    """Giro puro (v=0) deve dar w_esq == -w_dir."""
    v = 0.0
    omega = 1.0  # rad/s
    w_esq, w_dir = twist_to_wheel_speeds(v, omega)
    assert abs(w_esq + w_dir) < 1e-6


def test_joystick_center_zero():
    """Joystick no centro (0,0) → (v=0, ω=0)."""
    v, omega = joystick_to_twist(0.0, 0.0)
    assert abs(v) < 1e-6
    assert abs(omega) < 1e-6


def test_joystick_full_forward():
    """Joystick todo para frente (0,1) → v=MAX_LINEAR."""
    v, omega = joystick_to_twist(0.0, 1.0)
    assert abs(v - config.MAX_LINEAR_SPEED) < 1e-6
    assert abs(omega) < 1e-6


def test_joystick_full_right():
    """Joystick todo para a direita (1,0) → ω=MAX_ANGULAR."""
    v, omega = joystick_to_twist(1.0, 0.0)
    assert abs(v) < 1e-6
    assert abs(omega - config.MAX_ANGULAR_SPEED) < 1e-6


def test_joystick_saturation():
    """Valores >1 devem ser clamped a [-1,1]."""
    v, omega = joystick_to_twist(2.0, 2.0)
    assert v <= config.MAX_LINEAR_SPEED + 1e-6
    assert omega <= config.MAX_ANGULAR_SPEED + 1e-6


def test_roundtrip_twist():
    """twist → wheel_speeds → twist deve preservar v e ω."""
    v_in = 15.0  # cm/s
    omega_in = 1.5  # rad/s
    w_esq, w_dir = twist_to_wheel_speeds(v_in, omega_in)
    v_out, omega_out = wheel_speeds_to_twist(w_esq, w_dir)
    assert abs(v_out - v_in) < 1e-4
    assert abs(omega_out - omega_in) < 1e-4


def test_unit_consistency():
    """Verifica que as unidades são consistentes: v em cm/s, saída em rad/s.

    Com v=r (cm/s) e ω=0, w_esq = w_dir = v/r = 1 rad/s.
    """
    r = config.WHEEL_RADIUS_R_CM
    v = r
    omega = 0.0
    w_esq, w_dir = twist_to_wheel_speeds(v, omega)
    assert abs(w_esq - 1.0) < 1e-6
    assert abs(w_dir - 1.0) < 1e-6
