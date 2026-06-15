"""Injetor de falhas para a simulação.

Permite injetar/remover falhas em tempo real para teste de modos de segurança:
- Queda de serial (emulador para de responder).
- Tag oculta (visão sintética retorna não-detecção).
- Slip de roda (multiplicador por roda).
- Bateria saturada (dados de BMS falsos).

[ref: Seção 6b do mega-prompt]
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FaultState:
    """Estado atual das falhas injetadas."""

    serial_drop: bool = False
    tag_hidden: bool = False
    slip_esq: float = 1.0
    slip_dir: float = 1.0
    battery_saturated: bool = False


class FaultInjector:
    """Gerencia injeção de falhas nos componentes de simulação."""

    def __init__(self) -> None:
        self.state = FaultState()
        self._emulator = None
        self._vision = None
        self._world = None

    def bind(self, emulator: object, vision: object, world: object) -> None:
        """Vincula aos componentes de simulação."""
        self._emulator = emulator
        self._vision = vision
        self._world = world

    def inject_serial_drop(self, active: bool) -> None:
        """Injeta/remove queda de serial."""
        self.state.serial_drop = active
        if self._emulator is not None:
            self._emulator.set_serial_drop(active)

    def inject_tag_hidden(self, active: bool) -> None:
        """Injeta/remove ocultação da tag."""
        self.state.tag_hidden = active
        if self._vision is not None:
            self._vision.set_tag_hidden(active)

    def inject_wheel_slip(self, esq: float, dir_: float) -> None:
        """Define multiplicadores de slip por roda."""
        self.state.slip_esq = esq
        self.state.slip_dir = dir_
        if self._world is not None:
            self._world.set_slip(esq, dir_)

    def inject_battery_saturated(self, active: bool) -> None:
        """Injeta/remove saturação de bateria."""
        self.state.battery_saturated = active

    def clear_all(self) -> None:
        """Remove todas as falhas injetadas."""
        self.inject_serial_drop(False)
        self.inject_tag_hidden(False)
        self.inject_wheel_slip(1.0, 1.0)
        self.inject_battery_saturated(False)

    def get_state(self) -> dict:
        """Retorna estado das falhas para a UI."""
        return {
            "serial_drop": self.state.serial_drop,
            "tag_hidden": self.state.tag_hidden,
            "slip_esq": self.state.slip_esq,
            "slip_dir": self.state.slip_dir,
            "battery_saturated": self.state.battery_saturated,
        }
