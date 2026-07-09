"""Detecção de AprilTag (família `tag25h9`) com pupil-apriltags.

Encapsula o `Detector` e devolve as detecções cruas de um frame em tons de cinza.
A estimativa de pose (translação/rotação) fica em `pose.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from pupil_apriltags import Detector

from app import config

if TYPE_CHECKING:
    from pathlib import Path

    from app.vision.calibration import CameraIntrinsics


class AprilTagDetector:
    """Detector de AprilTag configurado para a família `tag25h9`."""

    def __init__(
        self,
        camera_params: tuple[float, float, float, float] | None = None,
        tag_size_m: float | None = None,
        *,
        intrinsics: "CameraIntrinsics | None" = None,
    ) -> None:
        """Cria o detector com a família e parâmetros de calibração.

        Args:
            camera_params: (fx, fy, cx, cy) em px. Se ``None``, usa ``intrinsics``
                ou, em último caso, ``config.CAMERA_PARAMS`` (placeholder).
            tag_size_m: tamanho físico da tag (m). Default: ``APRILTAG_SIZE_CM``.
            intrinsics: calibração carregada (tem prioridade sobre ``camera_params``).
        """
        self.tag_family: str = config.APRILTAG_FAMILY

        # Fallback = 0.04 (tag real medida: 4 cm — mesmo valor de
        # APRILTAG_SIZE_CM e do tag_size_m dos mapas; manter os três juntos).
        self.tag_size_m: float = (
            tag_size_m
            if tag_size_m is not None
            else ((config.APRILTAG_SIZE_CM / 100.0) if config.APRILTAG_SIZE_CM is not None else 0.04)
        )

        if intrinsics is not None:
            self.camera_params = intrinsics.camera_params
        elif camera_params is not None:
            self.camera_params = camera_params
        else:
            self.camera_params = config.CAMERA_PARAMS

        # Parâmetros de detecção. quad_decimate vem do config: a 1280×720 no
        # Pi, 2.0 corta ~4x o custo sem perder precisão de pose relevante.
        self.nthreads: int = 1
        self.quad_decimate: float = float(config.APRILTAG_QUAD_DECIMATE)
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

    @classmethod
    def from_calibration(
        cls,
        path: "Path | None" = None,
        tag_size_m: float | None = None,
    ) -> "AprilTagDetector":
        """Cria o detector a partir do JSON de calibração da câmera.

        Args:
            path: caminho do `camera_intrinsics.json`. Default: config.
            tag_size_m: tamanho físico da tag (m). Default: ``APRILTAG_SIZE_CM``.

        Raises:
            CalibrationError: se a câmera ainda não estiver calibrada.
        """
        from app.vision.calibration import load_intrinsics

        return cls(intrinsics=load_intrinsics(path), tag_size_m=tag_size_m)

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
