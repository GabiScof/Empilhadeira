"""Cinemática diferencial: (v, ω) → velocidades de roda (rad/s).

Especificação [ref: Seção 7 da AGENTS.md]:
    ω_esq = (v − ω·L/2) / r
    ω_dir = (v + ω·L/2) / r
onde `L` é a distância entre rodas e `r` o raio da roda (ver app/config.py).

No modo **manual**, o joystick (x, y) ∈ [-1, 1] vira (v, ω) com saturação
(`MAX_LINEAR_SPEED`, `MAX_ANGULAR_SPEED`). A saída (ω_esq, ω_dir) é a **mesma
interface nos dois modos** (manual e automático).

Premissa: rodas **sem escorregamento** (odometria degrada se patinar). [ref: Seção 4]
"""

from __future__ import annotations


def joystick_to_twist(x: float, y: float) -> tuple[float, float]:
    """Converte o joystick em velocidade linear e angular (modo manual).

    Args:
        x: componente de giro do joystick, [-1, 1].
        y: componente de avanço do joystick, [-1, 1].

    Returns:
        (v, ω): velocidade linear (cm/s) e angular (rad/s), já saturadas.
    """
    raise NotImplementedError


def twist_to_wheel_speeds(v: float, omega: float) -> tuple[float, float]:
    """Converte (v, ω) em velocidades angulares das rodas.

    Args:
        v: velocidade linear (cm/s).
        omega: velocidade angular (rad/s).

    Returns:
        (w_esq, w_dir): velocidades angulares das rodas (rad/s).
    """
    raise NotImplementedError
