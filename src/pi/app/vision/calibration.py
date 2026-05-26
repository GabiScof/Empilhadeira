"""Carregamento dos intrínsecos da câmera (saída da calibração).

Lê `calibracao/camera_intrinsics.json` (fx, fy, cx, cy, dist_coeffs) e o disponibiliza
para a estimativa de pose. Enquanto o arquivo estiver com valores null, a pose não
pode ser estimada — a calibração é `TODO(equipe)`.

[ref: docs/camera-calibration.md e Seção 3 da AGENTS.md]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CameraIntrinsics:
    """Parâmetros intrínsecos da câmera (em pixels).

    Atributos:
        fx, fy: distâncias focais (px).
        cx, cy: centro óptico (px).
        dist_coeffs: coeficientes de distorção.
    """

    fx: float
    fy: float
    cx: float
    cy: float
    dist_coeffs: list[float]


def load_intrinsics(path: Path) -> CameraIntrinsics:
    """Carrega os intrínsecos do JSON de calibração.

    Args:
        path: caminho do `camera_intrinsics.json`.

    Returns:
        CameraIntrinsics preenchido.

    Raises:
        ValueError: se o arquivo ainda estiver com valores null (não calibrado).
    """
    raise NotImplementedError
