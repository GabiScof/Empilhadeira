"""Tarefa de visão: captura frames, detecta AprilTag e estima a pose.

Roda na taxa permitida pela câmera/Pi (FPS depende do modelo do Pi — `TODO(equipe)`).
Produz uma `VisionState` (contrato 2, sub-objeto `visao`) e a publica no estado
compartilhado. Precisa lidar com perda de detecção perto do alvo (tag sai do FOV /
sai de foco com Z pequeno). [ref: Seção 4]

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio

import cv2

from app.state import SharedState
from app.vision.detector import AprilTagDetector
from app.vision.pose import estimate_vision_state


async def vision_loop(state: SharedState) -> None:
    """Loop da tarefa de visão (captura → detecção → pose → estado).

    Args:
        state: estado compartilhado entre as tarefas.
    """
    detector = AprilTagDetector()
    capture = cv2.VideoCapture(0)

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not capture.isOpened():
        raise RuntimeError("Camera did not open")

    try:
        while True:
            read_ok, frame = await asyncio.to_thread(capture.read)
            if not read_ok:
                await asyncio.sleep(0.01)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detections = detector.detect(gray)
            vision_state = estimate_vision_state(detections)
            state.update_vision(vision_state)

            print(
                f"visao detectado={vision_state.detectado} "
                f"id={vision_state.id} "
                f"x_cm={vision_state.x_cm} "
                f"z_cm={vision_state.z_cm} "
                f"pitch_deg={vision_state.pitch_deg}"
            )

            await asyncio.sleep(0)
    finally:
        capture.release()
