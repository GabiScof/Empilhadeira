"""Cinemática diferencial: joystick → twist → velocidades de roda.

Equações:
    ω_esq = (v − ω·L/2) / r
    ω_dir = (v + ω·L/2) / r

Unidades: v em cm/s, ω em rad/s, L em cm, r em cm, saída em rad/s.
"""

from __future__ import annotations

from app import config


def joystick_to_twist(x: float, y: float) -> tuple[float, float]:
    """Mapeia posição do joystick para velocidade linear e angular.

    Convenção do projeto (igual a twist_to_wheel_speeds/robot_model): ω positivo
    = giro ANTI-horário (virar à esquerda). Joystick x positivo = virar à
    direita, portanto ω = -x. O sinal foi validado na bancada em 2026-07-06:
    sem a negação, o modo manual virava para o lado oposto ao comandado.

    Args:
        x: componente de giro [-1, 1]. Positivo = virar à direita.
        y: componente de avanço [-1, 1]. Positivo = frente.

    Returns:
        (v_cm_s, omega_rad_s) com saturação em MAX_LINEAR_SPEED / MAX_ANGULAR_SPEED.
    """
    x = max(-1.0, min(1.0, x))
    y = max(-1.0, min(1.0, y))

    v = y * config.MAX_LINEAR_SPEED
    omega = -x * config.MAX_ANGULAR_SPEED

    v = max(-config.MAX_LINEAR_SPEED, min(config.MAX_LINEAR_SPEED, v))
    omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))

    return v, omega


def twist_to_wheel_speeds(v: float, omega: float) -> tuple[float, float]:
    """Converte twist (v, ω) em velocidades angulares das rodas.

    Args:
        v: velocidade linear em cm/s.
        omega: velocidade angular em rad/s.

    Returns:
        (w_esq, w_dir) em rad/s.
    """
    half_l = config.WHEEL_BASE_L_CM / 2.0
    r = config.WHEEL_RADIUS_R_CM

    w_esq = (v - omega * half_l) / r
    w_dir = (v + omega * half_l) / r

    return w_esq, w_dir


def wheel_speeds_to_twist(w_esq: float, w_dir: float) -> tuple[float, float]:
    """Inversa: velocidades de roda → twist (v, ω).

    Args:
        w_esq: velocidade angular roda esquerda (rad/s).
        w_dir: velocidade angular roda direita (rad/s).

    Returns:
        (v_cm_s, omega_rad_s).
    """
    r = config.WHEEL_RADIUS_R_CM
    half_l = config.WHEEL_BASE_L_CM / 2.0

    v = r * (w_esq + w_dir) / 2.0
    omega = r * (w_dir - w_esq) / (2.0 * half_l)

    return v, omega
