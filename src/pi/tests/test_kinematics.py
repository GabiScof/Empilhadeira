"""Estrutura de testes da cinemática diferencial (sem lógica real).

Os casos dependem de `L` e `r` (app/config.py), ainda `TODO(equipe)`.
[ref: Seção 7 e 11 da AGENTS.md]
"""

import pytest


@pytest.mark.skip(reason="TODO(equipe): definir L e r antes de testar a cinemática.")
def test_twist_to_wheel_speeds_straight() -> None:
    """Avanço puro (ω=0) deve dar w_esq == w_dir."""
    raise NotImplementedError


@pytest.mark.skip(reason="TODO: implementar após joystick_to_twist.")
def test_joystick_saturation() -> None:
    """Joystick no extremo deve saturar em MAX_LINEAR/MAX_ANGULAR."""
    raise NotImplementedError
