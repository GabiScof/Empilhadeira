"""Detecção de AprilTag (família `tag25h9`) com pupil-apriltags.

Encapsula o `Detector` e devolve as detecções cruas de um frame em tons de cinza.
A estimativa de pose (translação/rotação) fica em `pose.py`.

[ref: Seção 7 e 8 da AGENTS.md]
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pupil_apriltags import Detector

from app import config


class AprilTagDetector:
    """Detector de AprilTag configurado para a família `tag25h9`."""

    def __init__(self) -> None:
        """Cria o detector com a família e parâmetros de `config`.

        [ref: APRILTAG_FAMILY em app/config.py]
        """
        self.tag_family: str = config.APRILTAG_FAMILY

        # Valor de fallback até a equipe fechar APRILTAG_SIZE_CM.
        self.tag_size_m: float = (
            (config.APRILTAG_SIZE_CM / 100.0) if config.APRILTAG_SIZE_CM is not None else 0.05
        )

        self.camera_params: tuple[float, float, float, float] = config.CAMERA_PARAMS

        # Parâmetros de detecção mantidos do script-base.
        self.nthreads: int = 1
        self.quad_decimate: float = 1.0
        self.quad_sigma: float = 0.0
        self.refine_edges: int = 1
        self.decode_sharpening: float = 0.25
        self.debug: int = 0

        self._detector = Detector(
            families=self.tag_family,
            nthreads=self.nthreads,
            quad_decimate=self.quad_decimate,
            quad_sigma=self.quad_sigma,
            refine_edges=self.refine_edges,
            decode_sharpening=self.decode_sharpening,
            debug=self.debug,
        )

    def detect(self, gray: np.ndarray) -> list[Any]:
        """Detecta tags num frame em tons de cinza.

        Args:
            gray: imagem (H, W) uint8 em escala de cinza.

        Returns:
            Lista de detecções cruas do pupil-apriltags.
        """
        if gray.ndim != 2:
            raise ValueError("gray deve ser uma imagem 2D em escala de cinza")

        return self._detector.detect(
            gray,
            estimate_tag_pose=True,
            camera_params=self.camera_params,
            tag_size=self.tag_size_m,
        )
