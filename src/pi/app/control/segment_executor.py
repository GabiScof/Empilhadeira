"""Executor de segmentos de rota: FORWARD e TURN.

Malha externa de posição/heading (P/PI) sobre o EKF, ~20 Hz no Pi.
A malha interna de velocidade fica no ESP32 (~100 Hz) — não duplicar aqui.
"""

from __future__ import annotations

import math
from enum import StrEnum

from app import config
from app.control.path_planner import Segment, SegmentType


class ExecutorState(StrEnum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SEGMENT_DONE = "SEGMENT_DONE"
    ROUTE_DONE = "ROUTE_DONE"
    TIMEOUT = "TIMEOUT"


# Ganhos das malhas externas (centralizados em config — calibráveis pela equipe).
# Se os ganhos forem zero, o executor cai para velocidades fixas de fallback.
K_DIST: float = config.NAV_K_DIST  # ganho proporcional de distância → v
K_HEADING: float = config.NAV_K_HEADING  # ganho proporcional de heading → ω

FALLBACK_V_MS: float = config.NAV_FALLBACK_V_MS  # velocidade de avanço fixa (m/s)
FALLBACK_OMEGA_RADS: float = config.NAV_FALLBACK_OMEGA_RADS  # velocidade de giro fixa (rad/s)

POS_TOL_M: float = config.NAV_POS_TOL_M  # tolerância de posição (m)
HEADING_TOL_RAD: float = config.NAV_HEADING_TOL_RAD  # tolerância de heading (rad)

MIN_V_MS: float = config.NAV_MIN_V_MS  # piso anti atrito estático (reto)
MIN_OMEGA_RADS: float = config.NAV_MIN_OMEGA_RADS  # piso anti atrito (giro)
TURN_MAX_OMEGA_RADS: float = config.NAV_TURN_MAX_OMEGA_RADS  # teto anti derrapagem (giro)

MAX_SEGMENT_TIME_S: float = config.NAV_MAX_SEGMENT_TIME_S  # timeout por segmento


def _normalize_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


class SegmentExecutor:
    """Executa segmentos FORWARD/TURN produzindo setpoints de roda.

    Usa o EKF para feedback de posição e heading. Se os ganhos estão zerados
    (TODO(equipe)), usa velocidades fixas de fallback e confia nas tolerâncias.
    """

    def __init__(
        self,
        wheel_radius_m: float = 0.028,
        wheelbase_m: float = 0.15,
        max_v_ms: float = 0.30,
        max_omega_rads: float = 3.0,
    ) -> None:
        self._wheel_radius = wheel_radius_m
        self._wheelbase = wheelbase_m
        self._max_v = max_v_ms
        self._max_omega = max_omega_rads

        self._segments: list[Segment] = []
        self._current_idx: int = 0
        self._state = ExecutorState.IDLE
        self._elapsed_s: float = 0.0

        self._start_x: float = 0.0
        self._start_y: float = 0.0
        self._start_heading: float = 0.0
        self._accumulated_turn: float = 0.0
        self._last_heading: float = 0.0

    @property
    def state(self) -> ExecutorState:
        return self._state

    @property
    def current_segment(self) -> Segment | None:
        if 0 <= self._current_idx < len(self._segments):
            return self._segments[self._current_idx]
        return None

    @property
    def current_segment_index(self) -> int:
        return self._current_idx

    @property
    def total_segments(self) -> int:
        return len(self._segments)

    @property
    def progress(self) -> float:
        if not self._segments:
            return 1.0
        return self._current_idx / len(self._segments)

    def load_route(self, segments: list[Segment]) -> None:
        """Carrega uma nova rota para execução."""
        self._segments = list(segments)
        self._current_idx = 0
        self._state = ExecutorState.RUNNING if segments else ExecutorState.ROUTE_DONE
        self._elapsed_s = 0.0

    def step(
        self,
        x: float, y: float, theta: float,
        dt: float,
    ) -> tuple[float, float]:
        """Avança a execução e retorna setpoint (ω_esq, ω_dir) em rad/s.

        Args:
            x, y: posição atual estimada pelo EKF (m).
            theta: heading atual estimado (rad).
            dt: intervalo de tempo (s).

        Returns:
            (w_left, w_right) em rad/s para o setpoint do ESP32.
        """
        if self._state in (ExecutorState.IDLE, ExecutorState.ROUTE_DONE, ExecutorState.TIMEOUT):
            return 0.0, 0.0

        if self._current_idx >= len(self._segments):
            self._state = ExecutorState.ROUTE_DONE
            return 0.0, 0.0

        seg = self._segments[self._current_idx]
        self._elapsed_s += dt

        if self._elapsed_s > MAX_SEGMENT_TIME_S:
            self._state = ExecutorState.TIMEOUT
            return 0.0, 0.0

        if seg.type == SegmentType.FORWARD:
            v, omega = self._forward_step(seg, x, y, theta)
        else:
            v, omega = self._turn_step(seg, x, y, theta)

        return self._twist_to_wheels(v, omega)

    def _forward_step(
        self, seg: Segment, x: float, y: float, theta: float
    ) -> tuple[float, float]:
        """Malha externa de posição para segmento FORWARD."""
        dist_to_target = math.hypot(seg.target_x - x, seg.target_y - y)

        if dist_to_target < POS_TOL_M:
            self._advance_segment(x, y, theta)
            return 0.0, 0.0

        heading_to_target = math.atan2(seg.target_y - y, seg.target_x - x)
        heading_error = _normalize_angle(heading_to_target - theta)

        if K_DIST > 0:
            v = K_DIST * dist_to_target
        else:
            v = FALLBACK_V_MS

        # Piso anti atrito estático: proporcional puro comanda v minúsculo
        # perto do alvo e o robô real para antes da tolerância (bancada
        # 2026-07-07). Fora da tolerância, andar sempre acima do piso.
        v = max(v, MIN_V_MS)
        v = min(v, self._max_v)

        if abs(heading_error) > math.pi / 4:
            v = 0.0

        if K_HEADING > 0:
            omega = K_HEADING * heading_error
        else:
            omega = 2.0 * heading_error

        omega = max(-self._max_omega, min(self._max_omega, omega))

        return v, omega

    def _turn_step(
        self, seg: Segment, x: float, y: float, theta: float
    ) -> tuple[float, float]:
        """Malha externa de heading para segmento TURN."""
        heading_error = _normalize_angle(seg.target_heading - theta)

        if abs(heading_error) < HEADING_TOL_RAD:
            self._advance_segment(x, y, theta)
            return 0.0, 0.0

        if K_HEADING > 0:
            omega = K_HEADING * heading_error
        else:
            omega = FALLBACK_OMEGA_RADS * (1.0 if heading_error > 0 else -1.0)
            if abs(heading_error) < 0.3:
                omega *= abs(heading_error) / 0.3

        # Piso anti atrito estático no giro (skid steer precisa de torque):
        # sem isto o robô trava a poucos graus do alvo e estoura o timeout.
        # HEADING_TOL foi folgada (2°→4°) para o piso não oscilar na chegada.
        if abs(omega) < MIN_OMEGA_RADS:
            omega = MIN_OMEGA_RADS * (1.0 if heading_error > 0 else -1.0)

        # Teto anti derrapagem: giro no lugar rápido escorrega as rodas e
        # corrompe o θ da odometria (o avanço seguinte nasce torto). Janela
        # estreita piso–teto = giro consistente do início ao fim.
        turn_cap = min(self._max_omega, TURN_MAX_OMEGA_RADS)
        omega = max(-turn_cap, min(turn_cap, omega))

        return 0.0, omega

    def _advance_segment(self, x: float, y: float, theta: float) -> None:
        self._current_idx += 1
        self._elapsed_s = 0.0
        self._start_x = x
        self._start_y = y
        self._start_heading = theta
        self._last_heading = theta
        self._accumulated_turn = 0.0
        if self._current_idx >= len(self._segments):
            self._state = ExecutorState.ROUTE_DONE

    def _twist_to_wheels(self, v: float, omega: float) -> tuple[float, float]:
        """Converte (v, ω) em (ω_esq, ω_dir) via cinemática inversa."""
        r = self._wheel_radius
        half_l = self._wheelbase / 2.0
        w_left = (v - omega * half_l) / r
        w_right = (v + omega * half_l) / r
        return w_left, w_right

    def reset(self) -> None:
        """Reseta o executor."""
        self._segments = []
        self._current_idx = 0
        self._state = ExecutorState.IDLE
        self._elapsed_s = 0.0

    def to_dict(self) -> dict:
        seg = self.current_segment
        return {
            "state": self._state.value,
            "segment_index": self._current_idx,
            "total_segments": len(self._segments),
            "progress": round(self.progress, 2),
            "current_segment": seg.to_dict() if seg else None,
            "elapsed_s": round(self._elapsed_s, 2),
        }
