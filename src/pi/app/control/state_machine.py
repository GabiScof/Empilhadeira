"""Máquina de estados do robô: MANUAL / AUTOMATICO / PARADO.

Transições [ref: Seção 7 da AGENTS.md]:
- Operador alterna MANUAL ↔ AUTOMATICO.
- Condição de segurança → PARADO (rodas zeradas).
- Em AUTOMATICO, perder a tag por >TAG_LOST_FRAMES (~250 ms @20 Hz) → PARADO.
- Sair de PARADO exige ação explícita do operador (enviar MANUAL ou AUTOMATICO).
- Watchdog de comando no MANUAL: comando some com o robô andando → PARADO.

Latch de segurança: quando a PARADO é causada por uma condição de segurança (perda
de tag, watchdog, `force_stop`), ela **trava**. O loop de controle roda a 20 Hz e
re-propõe continuamente o modo selecionado pelo operador — sem o latch, isso
re-entraria no modo ativo todo tick (oscilação). O latch só é liberado por uma ação
explícita do operador (`acknowledge()`, chamada quando chega um comando de modo no
WebSocket). Como o frontend é orientado a evento, um comando de modo == ação humana.
"""

from __future__ import annotations

from app import config
from app.models import ForkCommand, Mode, VisionState


class StateMachine:
    """Máquina de estados com detecção de perda de tag e watchdog de comando."""

    def __init__(self) -> None:
        self._mode: Mode = Mode.PARADO
        self._tag_lost_count: int = 0
        self._last_command_time_ms: int = 0
        self._wheels_moving: bool = False
        self._safety_latched: bool = False

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def safety_latched(self) -> bool:
        """True se a PARADO atual foi disparada por segurança e exige acknowledge."""
        return self._safety_latched

    def acknowledge(self) -> None:
        """Ação explícita do operador: libera o latch de uma parada de segurança.

        Chamada pelo WebSocket handler quando chega um comando de modo do operador.
        Sem isso, a PARADO de segurança permanece travada e o robô não reativa.
        """
        self._safety_latched = False

    def step(
        self,
        requested_mode: Mode,
        vision: VisionState,
        garfo: ForkCommand,
        current_time_ms: int,
        w_esq: float = 0.0,
        w_dir: float = 0.0,
    ) -> tuple[Mode, float, float, ForkCommand]:
        """Avança a máquina de estados um passo.

        Args:
            requested_mode: modo desejado pelo operador.
            vision: estado atual da visão.
            garfo: comando do garfo (passa direto).
            current_time_ms: timestamp atual em ms.
            w_esq: velocidade da roda esquerda proposta (rad/s).
            w_dir: velocidade da roda direita proposta (rad/s).

        Returns:
            (mode, w_esq, w_dir, garfo) — estado resultante e setpoints.
        """
        self._wheels_moving = abs(w_esq) > 0.01 or abs(w_dir) > 0.01

        if requested_mode != self._mode:
            self._handle_transition(requested_mode, current_time_ms)

        if self._mode == Mode.AUTOMATICO:
            if not vision.detectado:
                self._tag_lost_count += 1
            else:
                self._tag_lost_count = 0

            if self._tag_lost_count > config.TAG_LOST_FRAMES:
                self._mode = Mode.PARADO
                self._tag_lost_count = 0
                self._safety_latched = True
                return self._mode, 0.0, 0.0, garfo

        if self._mode == Mode.MANUAL:
            self._last_command_time_ms = current_time_ms

        if self._mode == Mode.PARADO:
            return self._mode, 0.0, 0.0, garfo

        return self._mode, w_esq, w_dir, garfo

    def check_command_watchdog(self, current_time_ms: int) -> bool:
        """Verifica watchdog de comando no modo MANUAL.

        Returns:
            True se o watchdog disparou (transição para PARADO).
        """
        if self._mode != Mode.MANUAL:
            return False

        if not self._wheels_moving:
            return False

        elapsed = current_time_ms - self._last_command_time_ms
        if elapsed > config.COMMAND_WATCHDOG_MS:
            self._mode = Mode.PARADO
            self._safety_latched = True
            return True

        return False

    def force_stop(self) -> None:
        """Força o estado PARADO (chamado por condições de segurança)."""
        self._mode = Mode.PARADO
        self._tag_lost_count = 0
        self._safety_latched = True

    def _handle_transition(self, requested: Mode, current_time_ms: int) -> None:
        """Processa transição de estado."""
        if self._mode == Mode.PARADO:
            # Parada de segurança travada: o operador precisa reconhecer
            # explicitamente (acknowledge) antes de reativar. Sem isso, o loop de
            # controle re-entraria no modo ativo todo tick (oscilação).
            if self._safety_latched:
                return
            if requested in (Mode.MANUAL, Mode.AUTOMATICO):
                self._mode = requested
                self._tag_lost_count = 0
                self._last_command_time_ms = current_time_ms
        elif self._mode == Mode.MANUAL:
            if requested == Mode.AUTOMATICO:
                self._mode = Mode.AUTOMATICO
                self._tag_lost_count = 0
            elif requested == Mode.PARADO:
                self._mode = Mode.PARADO
        elif self._mode == Mode.AUTOMATICO:
            if requested == Mode.MANUAL:
                self._mode = Mode.MANUAL
                self._last_command_time_ms = current_time_ms
            elif requested == Mode.PARADO:
                self._mode = Mode.PARADO

    def update_command_time(self, current_time_ms: int) -> None:
        """Atualiza o timestamp do último comando recebido."""
        self._last_command_time_ms = current_time_ms
