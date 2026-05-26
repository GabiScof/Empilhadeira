"""Máquina de estados do robô: MANUAL / AUTOMATICO / PARADO.

Especificação [ref: Seção 7 da AGENTS.md]:
- O operador alterna **MANUAL ↔ AUTOMATICO**.
- Qualquer condição de segurança leva a **PARADO** (rodas zeradas).
- No **AUTOMATICO**, perder a tag por mais de `TAG_LOST_FRAMES` frames
  (~250 ms a 20 Hz) → **PARADO**.
- Sair de **PARADO** exige **ação explícita do operador** (não é automático).
- Watchdog de comando no MANUAL: perda de comando com o robô andando → PARADO.
"""

from __future__ import annotations

from app.models import Command, Mode, VisionState


class StateMachine:
    """Implementa as transições entre MANUAL, AUTOMATICO e PARADO."""

    def __init__(self) -> None:
        """Inicializa a máquina em PARADO."""
        raise NotImplementedError

    def step(
        self,
        command: Command | None,
        vision: VisionState,
        command_stale: bool,
    ) -> Mode:
        """Avalia uma transição de estado.

        Args:
            command: último comando do operador (ou None se nenhum).
            vision: última saída de visão (para detectar perda de tag).
            command_stale: True se o watchdog de comando expirou.

        Returns:
            Mode: o novo estado após aplicar as regras de transição.
        """
        raise NotImplementedError
