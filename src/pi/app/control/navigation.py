"""Navegação automática: posicionar o robô em frente à AprilTag.

Fases: COARSE_ALIGN → APPROACH → FACE → RETREAT (loop até convergir).

COARSE_ALIGN: |pitch|>45° causa ciclo-limite se ω for recalculado a cada frame;
gira com ω fixo até |pitch|<35° (histerese). APPROACH: centering por bearing,
transição para pitch perto do centro; convergência usa D verdadeiro. FACE corrige
equilíbrio falso perto do ZREF; RETREAT recua em linha reta até z>Z_RETREAT.
"""

from __future__ import annotations

import math
from collections import deque
from enum import Enum, auto

from app import config

_HEADING_GUARD_DEG: float = 30.0
_FOV_GUARD_RATIO: float = 0.70

_COARSE_ALIGN_ENTER_DEG: float = 45.0
_COARSE_ALIGN_EXIT_DEG: float = 35.0
_COARSE_ALIGN_OMEGA: float = 2.0

_CENTER_THRESH: float = 1.5
_CENTER_RANGE: float = 6.0
_CENTER_V_MIN: float = 0.15
_ALPHA_MIN: float = 0.30

_CONVERGE_Z_TOL: float = 2.0
_CONVERGE_D_TOL: float = 3.0
_CONVERGE_P_TOL: float = 5.0

_BEARING_KP: float = 0.20

_FACE_PITCH_TOL: float = 3.0
_FACE_KP_BOOST: float = 3.0
_FACE_TRIGGER_D: float = 2.5
_FACE_TRIGGER_TICKS: int = 15
_FACE_MIN_TICKS: int = 10
_FACE_X_ALIGNED: float = 2.0

_RETREAT_TARGET_Z: float = 30.0
_RETREAT_SPEED: float = 4.0

_OMEGA_SMOOTH: float = 0.5


class _Phase(Enum):
    COARSE_ALIGN = auto()
    APPROACH = auto()
    FACE = auto()
    RETREAT = auto()


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


def _center_v_scale(x_cm: float) -> float:
    ax = abs(x_cm)
    if ax <= _CENTER_THRESH:
        return 1.0
    t = min(1.0, (ax - _CENTER_THRESH) / (_CENTER_RANGE - _CENTER_THRESH))
    return 1.0 - t * (1.0 - _CENTER_V_MIN)


def _compute_twist(
    z_cm: float,
    x_cm: float,
    pitch_deg: float,
    *,
    allow_stuck_retreat: bool = False,
) -> tuple[float, float]:
    z_error = z_cm - config.ZREF_CM
    d_lat = _true_lateral(x_cm, z_cm, pitch_deg)

    if (
        abs(z_error) < _CONVERGE_Z_TOL
        and abs(d_lat) < _CONVERGE_D_TOL
        and abs(pitch_deg) < _CONVERGE_P_TOL
    ):
        return 0.0, 0.0

    v = config.NAV_KZ * z_error
    v = _decel_limited_v(v, z_cm)
    v = max(-config.MAX_LINEAR_SPEED, min(config.MAX_LINEAR_SPEED, v))

    if abs(pitch_deg) > _HEADING_GUARD_DEG:
        v = 0.0

    bg = _bearing_guard_scale(x_cm, z_cm)
    if v > 0:
        v *= bg

    if v > 0:
        v *= _center_v_scale(x_cm)

    if abs(x_cm) > _CENTER_THRESH:
        bearing_deg = math.degrees(math.atan2(x_cm, max(z_cm, 1.0)))
        omega = _BEARING_KP * bearing_deg
    else:
        omega = config.NAV_KP_PITCH * pitch_deg + _ALPHA_MIN * config.NAV_KX * x_cm

    omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))

    if allow_stuck_retreat and abs(v) < 0.5 and abs(omega) > 0.15:
        v = -2.0

    return v, omega


def compute_twist_primary(
    z_cm: float, x_cm: float, pitch_deg: float
) -> tuple[float, float]:
    return _compute_twist(z_cm, x_cm, pitch_deg, allow_stuck_retreat=False)


def compute_twist_fallback(
    z_cm: float, x_cm: float, pitch_deg: float
) -> tuple[float, float]:
    return _compute_twist(z_cm, x_cm, pitch_deg, allow_stuck_retreat=True)


class NavigationController:
    def __init__(self) -> None:
        self._omega_history: deque[float] = deque(maxlen=config.NAV_OSCILLATION_WINDOW)
        self._using_fallback: bool = False
        self._phase: _Phase = _Phase.APPROACH
        self._stall_counter: int = 0
        self._face_ticks: int = 0
        self._prev_omega: float = 0.0
        self._coarse_align_sign: float = 0.0

    def should_use_fallback(self, z_cm: float) -> bool:
        if z_cm < config.NAV_MIN_Z_FOR_PRIMARY:
            return True
        if len(self._omega_history) >= config.NAV_OSCILLATION_WINDOW:
            values = list(self._omega_history)
            sign_changes = sum(
                1
                for i in range(1, len(values))
                if values[i] * values[i - 1] < 0
            )
            if sign_changes >= config.NAV_OSCILLATION_WINDOW // 2:
                return True
        return False

    def compute(
        self, z_cm: float, x_cm: float, pitch_deg: float
    ) -> tuple[float, float]:
        d_lat = _true_lateral(x_cm, z_cm, pitch_deg)
        z_error = z_cm - config.ZREF_CM

        # ---- COARSE_ALIGN: fixed-omega rotation for large heading error ----
        if self._phase != _Phase.COARSE_ALIGN and abs(pitch_deg) > _COARSE_ALIGN_ENTER_DEG:
            self._phase = _Phase.COARSE_ALIGN
            self._coarse_align_sign = -1.0 if pitch_deg > 0 else 1.0

        if self._phase == _Phase.COARSE_ALIGN:
            if abs(pitch_deg) < _COARSE_ALIGN_EXIT_DEG:
                self._phase = _Phase.APPROACH
                self._stall_counter = 0
                self._prev_omega = 0.0
            else:
                omega = self._coarse_align_sign * _COARSE_ALIGN_OMEGA
                self._omega_history.append(omega)
                self._prev_omega = omega
                return 0.0, omega

        # ---- FACE: turn in place until heading is corrected ----
        if self._phase == _Phase.FACE:
            self._face_ticks += 1
            pitch_ok = abs(pitch_deg) < _FACE_PITCH_TOL
            min_time_met = self._face_ticks >= _FACE_MIN_TICKS

            if pitch_ok and min_time_met:
                if abs(x_cm) < _FACE_X_ALIGNED:
                    self._phase = _Phase.APPROACH
                    self._stall_counter = 0
                    self._prev_omega = 0.0
                else:
                    self._phase = _Phase.RETREAT
                    self._omega_history.append(0.0)
                    self._prev_omega = 0.0
                    return -_RETREAT_SPEED, 0.0

            omega = config.NAV_KP_PITCH * pitch_deg * _FACE_KP_BOOST
            omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))
            self._omega_history.append(omega)
            self._prev_omega = omega
            return 0.0, omega

        # ---- RETREAT: back straight until z > target ----
        if self._phase == _Phase.RETREAT:
            if z_cm >= _RETREAT_TARGET_Z:
                self._phase = _Phase.APPROACH
                self._stall_counter = 0
                self._prev_omega = 0.0
            self._omega_history.append(0.0)
            self._prev_omega = 0.0
            return -_RETREAT_SPEED, 0.0

        # ---- APPROACH ----
        near_zref = abs(z_error) < 5.0
        false_equil = abs(d_lat) > _FACE_TRIGGER_D and abs(x_cm) < _FACE_X_ALIGNED

        if near_zref and false_equil:
            self._stall_counter += 1
            if self._stall_counter >= _FACE_TRIGGER_TICKS:
                self._phase = _Phase.FACE
                self._face_ticks = 0
                omega = config.NAV_KP_PITCH * pitch_deg * _FACE_KP_BOOST
                omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))
                self._omega_history.append(omega)
                self._prev_omega = omega
                return 0.0, omega
        else:
            self._stall_counter = max(0, self._stall_counter - 1)

        self._using_fallback = self.should_use_fallback(z_cm)
        if self._using_fallback:
            v, omega = _compute_twist(
                z_cm, x_cm, pitch_deg, allow_stuck_retreat=True
            )
        else:
            v, omega = _compute_twist(
                z_cm, x_cm, pitch_deg, allow_stuck_retreat=False
            )

        if v != 0.0 or omega != 0.0:
            omega = _OMEGA_SMOOTH * omega + (1.0 - _OMEGA_SMOOTH) * self._prev_omega

        self._omega_history.append(omega)
        self._prev_omega = omega
        return v, omega

    def reset(self) -> None:
        self._omega_history.clear()
        self._using_fallback = False
        self._phase = _Phase.APPROACH
        self._stall_counter = 0
        self._face_ticks = 0
        self._prev_omega = 0.0
        self._coarse_align_sign = 0.0

    @property
    def using_fallback(self) -> bool:
        return self._using_fallback

    @property
    def retreating(self) -> bool:
        return self._phase == _Phase.RETREAT

    @property
    def phase(self) -> str:
        return self._phase.name
