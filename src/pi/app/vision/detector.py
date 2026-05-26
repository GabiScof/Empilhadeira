"""Detecção de AprilTag (família `tag25h9`) com pupil-apriltags.

Encapsula o `Detector` e devolve as detecções cruas de um frame em tons de cinza.
A estimativa de pose (translação/rotação) fica em `pose.py`.

[ref: Seção 7 e 8 da AGENTS.md]
"""

from __future__ import annotations

from typing import Any

import numpy as np


class AprilTagDetector:
    """Detector de AprilTag configurado para a família `tag25h9`."""

    def __init__(self) -> None:
        """Cria o detector com a família e parâmetros de `config`.

        [ref: APRILTAG_FAMILY em app/config.py]
        """
        raise NotImplementedError

    def detect(self, gray: np.ndarray) -> list[Any]:
        """Detecta tags num frame em tons de cinza.

        Args:
            gray: imagem (H, W) uint8 em escala de cinza.

        Returns:
            Lista de detecções cruas do pupil-apriltags.
        """
        raise NotImplementedError
