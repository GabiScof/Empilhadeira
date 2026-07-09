"""Máquina de estados de missão pick-and-place com garra MANUAL.

Fluxo:
  IDLE → LOAD_MAP → DRAW_TARGETS → GO_TO_PICK → AT_PICK(aguarda operador)
  → GO_TO_PLACE → AT_PLACE(aguarda operador) → GO_HOME → DONE

A garra NÃO é controlada automaticamente — nos estados AT_PICK e AT_PLACE
o robô para e o operador aciona a garra manualmente.
"""

from __future__ import annotations

import logging
import random
import time
from enum import StrEnum
from typing import TYPE_CHECKING

from app import config

if TYPE_CHECKING:
    from app.control.ekf import PoseEKF
    from app.control.path_planner import Segment
    from app.control.segment_executor import SegmentExecutor
    from app.world.world_model import WorldModel

logger = logging.getLogger(__name__)


class MissionState(StrEnum):
    """Estados da máquina de missão."""
    IDLE = "IDLE"
    LOAD_MAP = "LOAD_MAP"
    DRAW_TARGETS = "DRAW_TARGETS"
    GO_TO_PICK = "GO_TO_PICK"
    AT_PICK = "AT_PICK"
    GO_TO_PLACE = "GO_TO_PLACE"
    AT_PLACE = "AT_PLACE"
    GO_HOME = "GO_HOME"
    DONE = "DONE"
    FAULT = "FAULT"


class MissionSM:
    """Máquina de estados de missão com garra manual.

    O robô navega autonomamente entre tags, mas a garra é operada pelo
    operador humano nos estados AT_PICK e AT_PLACE.
    """

    def __init__(self) -> None:
        self._state = MissionState.IDLE
        self._pick_position_id: str | None = None
        self._place_position_id: str | None = None
        self._fault_reason: str | None = None
        self._operator_continue: bool = False
        self._world: "WorldModel | None" = None
        self._started_at: float = 0.0
        self._state_entered_at: float = 0.0
        self._navigation_ready: bool = False
        self._arrival_confirmed: bool = False
        self._seed: int = 42

    @property
    def state(self) -> MissionState:
        return self._state

    @property
    def pick_position_id(self) -> str | None:
        return self._pick_position_id

    @property
    def place_position_id(self) -> str | None:
        return self._place_position_id

    @property
    def fault_reason(self) -> str | None:
        return self._fault_reason

    @property
    def is_navigating(self) -> bool:
        return self._state in (
            MissionState.GO_TO_PICK,
            MissionState.GO_TO_PLACE,
            MissionState.GO_HOME,
        )

    @property
    def is_waiting_operator(self) -> bool:
        return self._state in (MissionState.AT_PICK, MissionState.AT_PLACE)

    @property
    def is_active(self) -> bool:
        return self._state not in (MissionState.IDLE, MissionState.DONE, MissionState.FAULT)

    def start_mission(self, world: "WorldModel", pick_id: str | None = None, place_id: str | None = None) -> bool:
        """Inicia uma nova missão.

        Args:
            world: modelo do mundo com mapa carregado.
            pick_id: position_id da tag de pick (None = sortear).
            place_id: position_id da tag de place (None = sortear).

        Returns:
            True se a missão foi iniciada com sucesso.
        """
        if self._state != MissionState.IDLE:
            logger.warning("Missão já em andamento (estado=%s)", self._state)
            return False

        self._world = world
        self._started_at = time.monotonic()
        self._transition(MissionState.LOAD_MAP)

        if len(world.tags) < 2:
            self._fault("Mapa tem menos de 2 tags — impossível sortear pick/place")
            return False

        self._transition(MissionState.DRAW_TARGETS)

        tag_ids = [t.position_id for t in world.tags]

        if pick_id and pick_id in tag_ids:
            self._pick_position_id = pick_id
        else:
            self._pick_position_id = None

        if place_id and place_id in tag_ids:
            self._place_position_id = place_id
        else:
            self._place_position_id = None

        # Padrão configurável (.env) antes do sorteio: prioridade
        # argumento explícito > padrão do config > sorteio por seed.
        if self._pick_position_id is None and config.MISSION_DEFAULT_PICK_ID in tag_ids:
            self._pick_position_id = config.MISSION_DEFAULT_PICK_ID

        rng = random.Random(self._seed)

        if self._pick_position_id is None:
            self._pick_position_id = rng.choice(tag_ids)

        remaining = [t for t in tag_ids if t != self._pick_position_id]
        if not remaining:
            self._fault("Apenas uma tag — não sobrou posição para place")
            return False

        if self._place_position_id is None and config.MISSION_DEFAULT_PLACE_ID in remaining:
            self._place_position_id = config.MISSION_DEFAULT_PLACE_ID

        if self._place_position_id is None:
            self._place_position_id = rng.choice(remaining)

        logger.info(
            "Missão: pick=%s, place=%s",
            self._pick_position_id,
            self._place_position_id,
        )

        self._transition(MissionState.GO_TO_PICK)
        self._navigation_ready = False
        return True

    def operator_continue(self) -> bool:
        """Operador clica 'continuar' — libera a transição de AT_PICK/AT_PLACE.

        Returns:
            True se o continue foi aceito.
        """
        if self._state == MissionState.AT_PICK:
            self._transition(MissionState.GO_TO_PLACE)
            self._navigation_ready = False
            return True
        elif self._state == MissionState.AT_PLACE:
            self._transition(MissionState.GO_HOME)
            self._navigation_ready = False
            return True
        return False

    def confirm_arrival(self) -> None:
        """Confirma que o robô chegou ao destino (chamado pelo executor)."""
        self._arrival_confirmed = True

    def notify_route_done(self) -> None:
        """Notifica que a rota foi concluída pelo executor."""
        if self._state == MissionState.GO_TO_PICK:
            self._transition(MissionState.AT_PICK)
            logger.info("Chegou ao ponto de pick — aguardando operador")
        elif self._state == MissionState.GO_TO_PLACE:
            self._transition(MissionState.AT_PLACE)
            logger.info("Chegou ao ponto de place — aguardando operador")
        elif self._state == MissionState.GO_HOME:
            self._transition(MissionState.DONE)
            elapsed = time.monotonic() - self._started_at
            logger.info("Missão concluída em %.1f s", elapsed)

    def get_current_target(self) -> tuple[float, float, float] | None:
        """Retorna a pose alvo atual (x_m, y_m, heading_rad) ou None.

        Para GO_TO_PICK e GO_TO_PLACE: ponto de approach na FRENTE da tag
        (standoff offset na direção que a tag aponta). O robô chega de frente
        para a face visível da tag — igual ao comportamento real com AprilTag.
        """
        if self._world is None:
            return None

        from app import config

        if self._state == MissionState.GO_TO_PICK:
            return self._world.tag_approach_pose_m_rad(
                self._pick_position_id or "",
                standoff_m=config.TAG_APPROACH_STANDOFF_M,
            )
        elif self._state == MissionState.GO_TO_PLACE:
            return self._world.tag_approach_pose_m_rad(
                self._place_position_id or "",
                standoff_m=config.TAG_APPROACH_STANDOFF_M,
            )
        elif self._state == MissionState.GO_HOME:
            return self._world.home_pose
        return None

    def fault(self, reason: str) -> None:
        """Entrada pública para registrar falha."""
        self._fault(reason)

    def _fault(self, reason: str) -> None:
        """Transição para FAULT."""
        self._fault_reason = reason
        self._transition(MissionState.FAULT)
        logger.error("FAULT: %s", reason)

    def reset(self) -> None:
        """Reseta a missão ao estado IDLE."""
        self._state = MissionState.IDLE
        self._pick_position_id = None
        self._place_position_id = None
        self._fault_reason = None
        self._operator_continue = False
        self._navigation_ready = False
        self._arrival_confirmed = False
        self._world = None

    def _transition(self, new_state: MissionState) -> None:
        logger.info("Missão: %s → %s", self._state, new_state)
        self._state = new_state
        self._state_entered_at = time.monotonic()
        self._arrival_confirmed = False

    def to_dict(self) -> dict:
        """Serializa para telemetria."""
        return {
            "state": self._state.value,
            "pick_position_id": self._pick_position_id,
            "place_position_id": self._place_position_id,
            "fault_reason": self._fault_reason,
            "is_navigating": self.is_navigating,
            "is_waiting_operator": self.is_waiting_operator,
            "elapsed_s": round(time.monotonic() - self._started_at, 1) if self._started_at else 0,
        }
