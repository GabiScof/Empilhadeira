"""Navegação automática: posicionar o robô em frente à AprilTag.

Estratégia A (primária): controle proporcional acoplado.
    v = Kz · (Z − Zref)
    ω = Kx · X + Kp_pitch · Pitch

Estratégia B (fallback): sequencial — alinhar(X→0) → aproximar(Z→Zref) → ajuste fino(Pitch→0).
Acionada quando A oscila/acopla ou quando Z está perto do limite do FOV/foco.

[ref: Seção 7 da AGENTS.md]
"""

from __future__ import annotations

from collections import deque

from app import config


def compute_twist_primary(z_cm: float, x_cm: float, pitch_deg: float) -> tuple[float, float]:
    """Estratégia A: controle proporcional acoplado.

    Args:
        z_cm: distância ao alvo (cm).
        x_cm: deslocamento lateral (cm, positivo = tag à direita).
        pitch_deg: orientação relativa (graus).

    Returns:
        (v_cm_s, omega_rad_s).
    """
    v = config.NAV_KZ * (z_cm - config.ZREF_CM)
    omega = config.NAV_KX * x_cm + config.NAV_KP_PITCH * pitch_deg

    v = max(-config.MAX_LINEAR_SPEED, min(config.MAX_LINEAR_SPEED, v))
    omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))

    return v, omega


def compute_twist_fallback(z_cm: float, x_cm: float, pitch_deg: float) -> tuple[float, float]:
    """Estratégia B: sequencial alinhar → aproximar → ajuste fino.

    Fases:
        1. Alinhar: corrigir X lateral até |X| < tolerância.
        2. Aproximar: avançar/recuar até Z ≈ Zref.
        3. Ajuste fino: corrigir Pitch até |Pitch| < tolerância.

    Args:
        z_cm: distância ao alvo (cm).
        x_cm: deslocamento lateral (cm).
        pitch_deg: orientação relativa (graus).

    Returns:
        (v_cm_s, omega_rad_s).
    """
    v = 0.0
    omega = 0.0

    if abs(x_cm) > config.NAV_ALIGN_X_TOL:
        omega = config.NAV_KX * x_cm
        omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))
        return v, omega

    z_error = z_cm - config.ZREF_CM
    if abs(z_error) > 1.0:
        v = config.NAV_KZ * z_error
        v = max(-config.MAX_LINEAR_SPEED, min(config.MAX_LINEAR_SPEED, v))
        return v, omega

    if abs(pitch_deg) > config.NAV_ALIGN_PITCH_TOL:
        omega = config.NAV_KP_PITCH * pitch_deg
        omega = max(-config.MAX_ANGULAR_SPEED, min(config.MAX_ANGULAR_SPEED, omega))

    return v, omega


class NavigationController:
    """Controlador de navegação com troca automática entre estratégias A e B."""

    def __init__(self) -> None:
        self._omega_history: deque[float] = deque(maxlen=config.NAV_OSCILLATION_WINDOW)
        self._using_fallback: bool = False

    def should_use_fallback(self, z_cm: float) -> bool:
        """Determina se deve usar fallback baseado em oscilação ou proximidade.

        Args:
            z_cm: distância atual ao alvo (cm).

        Returns:
            True se deve usar estratégia B.
        """
        if z_cm < config.NAV_MIN_Z_FOR_PRIMARY:
            return True

        if len(self._omega_history) >= config.NAV_OSCILLATION_WINDOW:
            values = list(self._omega_history)
            sign_changes = sum(1 for i in range(1, len(values)) if values[i] * values[i - 1] < 0)
            if sign_changes >= config.NAV_OSCILLATION_WINDOW // 2:
                return True

        return False

    def compute(self, z_cm: float, x_cm: float, pitch_deg: float) -> tuple[float, float]:
        """Calcula twist de navegação, escolhendo estratégia A ou B.

        Args:
            z_cm: distância ao alvo (cm).
            x_cm: deslocamento lateral (cm).
            pitch_deg: orientação relativa (graus).

        Returns:
            (v_cm_s, omega_rad_s).
        """
        self._using_fallback = self.should_use_fallback(z_cm)

        if self._using_fallback:
            v, omega = compute_twist_fallback(z_cm, x_cm, pitch_deg)
        else:
            v, omega = compute_twist_primary(z_cm, x_cm, pitch_deg)

        self._omega_history.append(omega)
        return v, omega

    def reset(self) -> None:
        """Reseta o histórico de oscilação."""
        self._omega_history.clear()
        self._using_fallback = False

    @property
    def using_fallback(self) -> bool:
        return self._using_fallback
