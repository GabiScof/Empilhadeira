"""Carregamento dos intrínsecos da câmera (saída da calibração).

Lê `calibracao/camera_intrinsics.json` (fx, fy, cx, cy, dist_coeffs) e o disponibiliza
para a estimativa de pose. Enquanto o arquivo estiver com valores ``null``, a câmera
ainda não foi calibrada e a pose **não** pode ser estimada de forma confiável.

Contrato esperado do JSON (gerado por `docs/camera-calibration.md`):

    {
      "fx": 1234.5, "fy": 1234.5,           # distâncias focais (px) — obrigatórios
      "cx": 640.0,  "cy": 360.0,            # centro óptico (px)     — obrigatórios
      "dist_coeffs": [k1, k2, p1, p2, k3],  # opcional; default = sem distorção
      "image_size": [1280, 720],           # opcional (metadados)
      "reprojection_error": 0.31            # opcional (qualidade da calibração)
    }

[ref: docs/camera-calibration.md e Seção 3 da AGENTS.md]
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Campos obrigatórios para uma calibração utilizável.
_REQUIRED_FIELDS: tuple[str, ...] = ("fx", "fy", "cx", "cy")


class CalibrationError(RuntimeError):
    """A calibração da câmera está ausente, incompleta ou inválida.

    Lançada quando o JSON de intrínsecos não existe, não pôde ser lido, ou ainda
    contém valores ``null`` (a equipe ainda não rodou a calibração). A mensagem
    inclui a ação corretiva (rodar a calibração).
    """


@dataclass(frozen=True)
class CameraIntrinsics:
    """Parâmetros intrínsecos da câmera (em pixels).

    Atributos:
        fx, fy: distâncias focais (px).
        cx, cy: centro óptico (px).
        dist_coeffs: coeficientes de distorção (default = sem distorção).
        image_size: (largura, altura) em px, se disponível.
        reprojection_error: erro de reprojeção da calibração, se disponível.
    """

    fx: float
    fy: float
    cx: float
    cy: float
    dist_coeffs: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0, 0.0])
    image_size: tuple[int, int] | None = None
    reprojection_error: float | None = None

    @property
    def camera_params(self) -> tuple[float, float, float, float]:
        """Tupla (fx, fy, cx, cy) no formato esperado por pupil-apriltags."""
        return (self.fx, self.fy, self.cx, self.cy)

    @property
    def camera_matrix(self) -> Any:
        """Matriz intrínseca 3x3 (numpy) para uso com OpenCV."""
        import numpy as np

        return np.array(
            [[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]],
            dtype=float,
        )


def load_intrinsics(path: Path | None = None) -> CameraIntrinsics:
    """Carrega os intrínsecos do JSON de calibração.

    Args:
        path: caminho do `camera_intrinsics.json`. Se ``None``, usa
            ``config.CAMERA_INTRINSICS_PATH``.

    Returns:
        CameraIntrinsics preenchido.

    Raises:
        CalibrationError: se o arquivo não existir, não puder ser lido, ou ainda
            estiver com valores ``null`` (não calibrado).
    """
    if path is None:
        from app import config

        path = config.CAMERA_INTRINSICS_PATH

    path = Path(path)
    if not path.exists():
        raise CalibrationError(
            f"Arquivo de calibração não encontrado: {path}. "
            "Rode a calibração da câmera (ver docs/camera-calibration.md)."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise CalibrationError(f"Falha ao ler {path}: {exc}") from exc

    missing = [key for key in _REQUIRED_FIELDS if data.get(key) is None]
    if missing:
        raise CalibrationError(
            f"Calibração incompleta em {path}: campos {missing} estão null. "
            "Rode a calibração da câmera (ver docs/camera-calibration.md)."
        )

    raw_image_size = data.get("image_size")
    image_size: tuple[int, int] | None = None
    if isinstance(raw_image_size, (list, tuple)) and len(raw_image_size) == 2:
        image_size = (int(raw_image_size[0]), int(raw_image_size[1]))

    dist = data.get("dist_coeffs")
    if isinstance(dist, dict):
        # Formato dict: {"k1":..,"k2":..,"k3":..,"p1":..,"p2":..}. OpenCV espera
        # a ordem [k1, k2, p1, p2, k3].
        dist_coeffs = [float(dist.get(k, 0.0)) for k in ("k1", "k2", "p1", "p2", "k3")]
    elif dist:
        dist_coeffs = [float(c) for c in dist]
    else:
        dist_coeffs = [0.0, 0.0, 0.0, 0.0, 0.0]

    return CameraIntrinsics(
        fx=float(data["fx"]),
        fy=float(data["fy"]),
        cx=float(data["cx"]),
        cy=float(data["cy"]),
        dist_coeffs=dist_coeffs,
        image_size=image_size,
        reprojection_error=(
            float(data["reprojection_error"])
            if data.get("reprojection_error") is not None
            else None
        ),
    )


def load_intrinsics_or_none(path: Path | None = None) -> CameraIntrinsics | None:
    """Igual a :func:`load_intrinsics`, mas retorna ``None`` se não calibrado."""
    try:
        return load_intrinsics(path)
    except CalibrationError:
        return None


def is_calibrated(path: Path | None = None) -> bool:
    """Retorna ``True`` se há uma calibração utilizável no caminho dado."""
    return load_intrinsics_or_none(path) is not None


def calibration_image_size(path: Path | None = None) -> tuple[int, int] | None:
    """Resolução (largura, altura) em que a câmera foi CALIBRADA, se anotada.

    Os intrínsecos fx/fy/cx/cy só valem nessa resolução: capturar em outra
    produz z/x silenciosamente errados. Quem abre a câmera deve preferir este
    tamanho ao do config/env (armadilha vista na bancada em 2026-07-07:
    default 1280x720 com calibração 640x480).
    """
    intr = load_intrinsics_or_none(path)
    if intr is None or intr.image_size is None:
        return None
    return int(intr.image_size[0]), int(intr.image_size[1])
