"""Tarefa de visão: captura frames, detecta AprilTag e estima a pose.

Suporta injeção de fonte de visão: detector real (OpenCV+pupil-apriltags) ou
visão sintética (SIM=1). A interface do detector é injetável via argumento.

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from app.models import VisionState
from app.state import SharedState

logger = logging.getLogger(__name__)


class VisionSource(Protocol):
    """Interface para fontes de visão injetáveis."""

    def get_vision(self) -> VisionState:
        """Retorna o estado de visão atual."""
        ...


class RealVisionSource:
    """Fonte de visão real usando OpenCV + pupil-apriltags."""

    def __init__(self) -> None:
        import cv2

        from app.vision.detector import AprilTagDetector
        from app.vision.pose import estimate_vision_state

        self._detector = AprilTagDetector()
        self._estimate = estimate_vision_state
        self._capture = cv2.VideoCapture(0)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self._cv2 = cv2

        if not self._capture.isOpened():
            raise RuntimeError("Câmera não abriu")

    def get_vision(self) -> VisionState:
        read_ok, frame = self._capture.read()
        if not read_ok:
            return VisionState()

        gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        detections = self._detector.detect(gray)
        return self._estimate(detections)

    def release(self) -> None:
        self._capture.release()


class SimVisionSource:
    """Fonte de visão sintética para SIM=1."""

    def __init__(self, synthetic_vision: object, world: object) -> None:
        self._vision = synthetic_vision
        self._world = world

    def get_vision(self) -> VisionState:
        from app.sim.synthetic_vision import SyntheticVision
        from app.sim.world import SimWorld

        if not isinstance(self._vision, SyntheticVision) or not isinstance(self._world, SimWorld):
            return VisionState()

        return self._vision.compute(
            robot_x=self._world.robot_x,
            robot_y=self._world.robot_y,
            robot_theta=self._world.robot_theta,
            tag_x=self._world.tag_x,
            tag_y=self._world.tag_y,
            tag_theta=self._world.tag_theta,
            tag_id=self._world.tag_id,
        )


async def vision_loop(state: SharedState, source: VisionSource) -> None:
    """Loop da tarefa de visão.

    Args:
        state: estado compartilhado entre as tarefas.
        source: fonte de visão injetável (real ou sintética).
    """
    logger.info("Vision loop iniciado")

    try:
        while True:
            vision_state = source.get_vision()
            await state.update_vision(vision_state)
            await asyncio.sleep(1.0 / 20.0)
    except asyncio.CancelledError:
        logger.info("Vision loop cancelado")
    finally:
        if isinstance(source, RealVisionSource):
            source.release()
