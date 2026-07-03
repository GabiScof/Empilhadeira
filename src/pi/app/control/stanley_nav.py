"""Stanley/Unified path-following controller for tag approach.

Alternative to the reactive NavigationController. Instead of switching between
bearing-only and pitch-only modes, this controller ALWAYS combines both
corrections in one formula:

    ω = K_bearing · bearing_angle + K_pitch · pitch_angle

Plus FACE/RETREAT at the goal when false equilibrium is detected.

Key difference from reactive:
  - During approach: bearing AND pitch are ALWAYS both active
  - Reactive switches: bearing-only when |x|>1.5, pitch+x when |x|≤1.5
  - The unified formula is smoother (no threshold switching) but slightly
    slower because pitch and bearing corrections can partially cancel.

This module exists for comparison/experimentation only.
The existing NavigationController should remain the primary controller.

[ref: Seção 7 da AGENTS.md — alternativa experimental]
"""

from __future__ import annotations

import math
from collections import deque

from app import config

_CONVERGE_Z_TOL: float = 2.0
_CONVERGE_D_TOL: float = 3.0
_CONVERGE_P_TOL: float = 5.0

_HEADING_GUARD_DEG: float = 30.0
_FOV_GUARD_RATIO: float = 0.70

_CENTER_THRESH: float = 1.5
_CENTER_RANGE: float = 6.0
_CENTER_V_MIN: float = 0.15


def _true_lateral(x_cm: float, z_cm: float, pitch_deg: float) -> float:
    z_ref = min(z_cm, config.ZREF_CM)
    return x_cm - z_ref * math.sin(math.radians(pitch_deg))


def _decel_limited_v(v: float, z_cm: float) -> float:
    d = abs(z_cm - config.ZREF_CM)
    if d < 0.1:
        return 0.0
    v_max = math.sqrt(2.0 * config.NAV_DECEL_CMS2 * d)
    v_max = min(v_max, config.NAV_MAX_APPROACH_SPEED)
    if v > 0:
        return min(v, v_max)
    return max(v, -v_max)


def _bearing_guard_scale(x_cm: float, z_cm: float) -> float:
    if z_cm <= 0:
        return 1.0
    bearing_deg = abs(math.degrees(math.atan2(x_cm, z_cm)))
    fov_half = config.SIM_VISION_FOV_H_DEG / 2.0
    guard_start = fov_half * _FOV_GUARD_RATIO
    if bearing_deg <= guard_start:
        return 1.0
    if bearing_deg >= fov_half:
        return 0.0
    return (fov_half - bearing_deg) / (fov_half - guard_start)


class StanleyNav:
    """Unified bearing+pitch controller with FACE/RETREAT at goal.

    Approach: ω = K_bearing · bearing° + K_pitch · pitch°
    Near goal: FACE (turn in place) + RETREAT (back up) when stuck.
    """

    K_BEARING: float = 0.20
    K_PITCH: float = 0.10
    K_FACE_BOOST: float = 3.0
    FACE_PITCH_TOL: float = 3.0
    FACE_MIN_TICKS: int = 10
    FACE_X_ALIGNED: float = 2.0
    RETREAT_SPEED: float = 4.0
    RETREAT_TARGET_Z: float = 30.0
    OMEGA_SMOOTH: float = 0.5
    STALL_TICKS: int = 15
    FACE_TRIGGER_D: float = 2.5

    def __init__(self) -> None:
        self._prev_omega: float = 0.0
        self._omega_history: deque[float] = deque(maxlen=config.NAV_OSCILLATION_WINDOW)
        self._stall_counter: int = 0
        self._facing: bool = False
        self._face_ticks: int = 0
        self._retreating: bool = False

    def compute(
        self, z_cm: float, x_cm: float, pitch_deg: float
    ) -> tuple[float, float]:
        z_error = z_cm - config.ZREF_CM
        d_lat = _true_lateral(x_cm, z_cm, pitch_deg)

        if (
            abs(z_error) < _CONVERGE_Z_TOL
            and abs(d_lat) < _CONVERGE_D_TOL
            and abs(pitch_deg) < _CONVERGE_P_TOL
        ):
            self._prev_omega = 0.0
            self._stall_counter = 0
            self._facing = False
            self._retreating = False
            return 0.0, 0.0

        # --- FACE: turn in place to correct heading ---
        if self._facing:
            self._face_ticks += 1
            pitch_ok = abs(pitch_deg) < self.FACE_PITCH_TOL
            time_ok = self._face_ticks >= self.FACE_MIN_TICKS

            if pitch_ok and time_ok:
                self._facing = False
                if abs(x_cm) < self.FACE_X_ALIGNED:
                    self._stall_counter = 0
                    self._prev_omega = 0.0
                else:
                    self._retreating = True
                    self._prev_omega = 0.0
                    return -self.RETREAT_SPEED, 0.0

            omega = config.NAV_KP_PITCH * pitch_deg * self.K_FACE_BOOST
            omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))
            self._omega_history.append(omega)
            self._prev_omega = omega
            return 0.0, omega

        # --- RETREAT: back up straight ---
        if self._retreating:
            if z_cm >= self.RETREAT_TARGET_Z:
                self._retreating = False
                self._stall_counter = 0
                self._prev_omega = 0.0
            self._omega_history.append(0.0)
            self._prev_omega = 0.0
            return -self.RETREAT_SPEED, 0.0

        # --- APPROACH: unified bearing + pitch ---
        near_zref = abs(z_error) < 5.0
        false_equil = (
            (abs(d_lat) > self.FACE_TRIGGER_D and abs(x_cm) < self.FACE_X_ALIGNED)
            or (abs(d_lat) > _CONVERGE_D_TOL and abs(pitch_deg) > _CONVERGE_P_TOL * 2)
        )

        if near_zref and false_equil:
            self._stall_counter += 1
            if self._stall_counter >= self.STALL_TICKS:
                self._facing = True
                self._face_ticks = 0
                omega = config.NAV_KP_PITCH * pitch_deg * self.K_FACE_BOOST
                omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))
                self._omega_history.append(omega)
                self._prev_omega = omega
                return 0.0, omega
        else:
            self._stall_counter = max(0, self._stall_counter - 1)

        v = config.NAV_KZ * z_error
        v = _decel_limited_v(v, z_cm)
        v = max(-config.MAX_LINEAR_SPEED, min(config.MAX_LINEAR_SPEED, v))

        if abs(pitch_deg) > _HEADING_GUARD_DEG:
            v = 0.0

        bg = _bearing_guard_scale(x_cm, z_cm)
        if v > 0:
            v *= bg

        ax = abs(x_cm)
        if v > 0 and ax > _CENTER_THRESH:
            t = min(1.0, (ax - _CENTER_THRESH) / (_CENTER_RANGE - _CENTER_THRESH))
            v *= 1.0 - t * (1.0 - _CENTER_V_MIN)

        bearing_deg = math.degrees(math.atan2(x_cm, max(z_cm, 1.0)))
        center_blend = max(0.0, min(1.0, 1.0 - (abs(x_cm) - _CENTER_THRESH) / 3.0))
        omega_centering = self.K_BEARING * bearing_deg
        omega_alignment = config.NAV_KP_PITCH * pitch_deg + 0.30 * config.NAV_KX * x_cm
        omega = (1.0 - center_blend) * omega_centering + center_blend * omega_alignment
        omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))

        if v != 0.0 or omega != 0.0:
            omega = (
                self.OMEGA_SMOOTH * omega
                + (1.0 - self.OMEGA_SMOOTH) * self._prev_omega
            )

        self._omega_history.append(omega)
        self._prev_omega = omega
        return v, omega

    def reset(self) -> None:
        self._prev_omega = 0.0
        self._omega_history.clear()
        self._stall_counter = 0
        self._facing = False
        self._face_ticks = 0
        self._retreating = False

    @property
    def phase(self) -> str:
        if self._facing:
            return "FACE"
        if self._retreating:
            return "RETREAT"
        return "STANLEY"
