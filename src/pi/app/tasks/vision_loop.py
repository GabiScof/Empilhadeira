"""Tarefa de visão: captura frames, detecta AprilTag e estima a pose.

Roda na taxa permitida pela câmera/Pi (FPS depende do modelo do Pi — `TODO(equipe)`).
Produz uma `VisionState` (contrato 2, sub-objeto `visao`) e a publica no estado
compartilhado. Precisa lidar com perda de detecção perto do alvo (tag sai do FOV /
sai de foco com Z pequeno). [ref: Seção 4]

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

from app.state import SharedState


async def vision_loop(state: SharedState) -> None:
    """Loop da tarefa de visão (captura → detecção → pose → estado).

    Args:
        state: estado compartilhado entre as tarefas.
    """
    raise NotImplementedError
