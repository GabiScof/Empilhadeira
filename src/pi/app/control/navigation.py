"""Navegação automática: posiciona o robô em frente ao alvo (AprilTag).

Objetivo: X≈0, Pitch≈0, Z≈Zref. [ref: Seção 7 da AGENTS.md]

**Abordagem A (primária)** — controle proporcional acoplado:
    v = Kz · (Z − Zref)
    ω = Kx · X + Kp_pitch · Pitch
Risco conhecido: os termos `Kx·X` e `Kp_pitch·Pitch` em ω podem **acoplar/brigar**;
prever fallback. [ref: Seção 4]

**Abordagem B (fallback)** — sequencial: (1) alinhar (X→0), (2) aproximar (Z→Zref),
(3) ajuste fino de orientação (Pitch→0), em etapas discretas.

Ganhos (`Kz`, `Kx`, `Kp_pitch`) e `Zref` em app/config.py (`TODO(equipe)`).
Tratar perda de tag perto do alvo (Z pequeno) delegando à máquina de estados.
"""

from __future__ import annotations

from app.models import VisionState


def compute_twist_primary(vision: VisionState) -> tuple[float, float]:
    """Abordagem A: controle proporcional acoplado a partir da visão.

    Args:
        vision: pose atual da tag (z_cm, x_cm, pitch_deg).

    Returns:
        (v, ω): velocidade linear (cm/s) e angular (rad/s).
    """
    raise NotImplementedError


def compute_twist_fallback(vision: VisionState) -> tuple[float, float]:
    """Abordagem B: navegação sequencial alinhar → aproximar → ajuste fino.

    Args:
        vision: pose atual da tag (z_cm, x_cm, pitch_deg).

    Returns:
        (v, ω): velocidade linear (cm/s) e angular (rad/s).
    """
    raise NotImplementedError
