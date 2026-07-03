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
    vision_blur_prob: float = 0.0
    vision_drop_prob: float = 0.0
    encoder_noise_std: float = 0.05
    gyro_drift_rads: float = 0.001


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

    def inject_vision_blur(self, prob: float) -> None:
        """Injeta probabilidade de motion blur."""
        self.state.vision_blur_prob = prob
        if self._vision is not None and hasattr(self._vision, 'set_blur_prob'):
            self._vision.set_blur_prob(prob)

    def inject_vision_drop(self, prob: float) -> None:
        """Injeta probabilidade de drop (sem detecção)."""
        self.state.vision_drop_prob = prob
        if self._vision is not None and hasattr(self._vision, 'set_drop_prob'):
            self._vision.set_drop_prob(prob)

    def inject_encoder_noise(self, std: float) -> None:
        """Injeta ruído de encoder."""
        self.state.encoder_noise_std = std
        if self._world is not None and hasattr(self._world, 'encoder_noise_std'):
            self._world.encoder_noise_std = std

    def inject_gyro_drift(self, drift: float) -> None:
        """Injeta drift do giroscópio."""
        self.state.gyro_drift_rads = drift
        if self._world is not None and hasattr(self._world, 'gyro_drift_rads'):
            self._world.gyro_drift_rads = drift

    def clear_all(self) -> None:
        """Remove todas as falhas injetadas."""
        self.inject_serial_drop(False)
        self.inject_tag_hidden(False)
        self.inject_wheel_slip(1.0, 1.0)
        self.inject_battery_saturated(False)
        self.inject_vision_blur(0.0)
        self.inject_vision_drop(0.0)
        self.inject_encoder_noise(0.05)
        self.inject_gyro_drift(0.001)

    def get_state(self) -> dict:
        """Retorna estado das falhas para a UI."""
        return {
            "serial_drop": self.state.serial_drop,
            "tag_hidden": self.state.tag_hidden,
            "slip_esq": self.state.slip_esq,
            "slip_dir": self.state.slip_dir,
            "battery_saturated": self.state.battery_saturated,
            "vision_blur_prob": self.state.vision_blur_prob,
            "vision_drop_prob": self.state.vision_drop_prob,
            "encoder_noise_std": self.state.encoder_noise_std,
            "gyro_drift_rads": self.state.gyro_drift_rads,
        }
