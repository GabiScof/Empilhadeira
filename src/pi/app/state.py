"""Estado compartilhado entre as três tarefas asyncio do backend.

Guarda o último comando recebido do frontend, a última leitura de sensores do
ESP32, a última saída de visão e o estado atual da máquina de estados. Serve de
ponto único de leitura/escrita coordenada entre WebSocket Handler, Vision Loop e
Serial Loop.

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import time

from app.control.kalman import AttitudeKalman
from app.control.navigation import NavigationController
from app.control.state_machine import StateMachine
from app.models import (
    Battery,
    Command,
    ImuAngles,
    Mode,
    Sensors,
    Setpoint,
    Telemetry,
    VisionState,
    WheelSpeeds,
)
from app.telemetry.aggregator import build_telemetry


class SharedState:
    """Estado compartilhado, protegido por lock asyncio para acesso concorrente."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.state_machine = StateMachine()
        self.kalman = AttitudeKalman()
        self.navigator = NavigationController()

        self.last_command: Command | None = None
        self.last_sensors: Sensors | None = None
        self.last_vision: VisionState = VisionState()
        self.last_imu: ImuAngles = ImuAngles(roll=0.0, pitch=0.0)

        self.current_setpoint: Setpoint = Setpoint(w_esq=0.0, w_dir=0.0)

    @property
    def mode(self) -> Mode:
        return self.state_machine.mode

    async def update_command(self, command: Command) -> None:
        """Registra o último comando do frontend."""
        async with self.lock:
            self.last_command = command

    async def clear_command(self) -> None:
        """Limpa a intenção do operador (ex.: ao cair a conexão WebSocket)."""
        async with self.lock:
            self.last_command = None

    async def update_sensors(self, sensors: Sensors) -> None:
        """Registra a última leitura de sensores do ESP32."""
        async with self.lock:
            self.last_sensors = sensors

    async def update_vision(self, vision: VisionState) -> None:
        """Registra a última saída de visão."""
        async with self.lock:
            self.last_vision = vision

    async def update_imu(self, imu: ImuAngles) -> None:
        """Registra o roll/pitch filtrado pelo Kalman."""
        async with self.lock:
            self.last_imu = imu

    async def update_setpoint(self, setpoint: Setpoint) -> None:
        """Registra o setpoint atual a enviar ao ESP32."""
        async with self.lock:
            self.current_setpoint = setpoint

    async def snapshot_telemetry(self) -> Telemetry:
        """Monta um snapshot de telemetria a partir do estado atual."""
        async with self.lock:
            if self.last_sensors is not None:
                rodas = WheelSpeeds(
                    esq=self.last_sensors.enc.esq,
                    dir=self.last_sensors.enc.dir,
                )
            else:
                rodas = WheelSpeeds(esq=0.0, dir=0.0)

            bateria = Battery()
            if self.last_sensors is not None and self.last_sensors.bms is not None:
                bateria = self.last_sensors.bms

            return build_telemetry(
                estado=self.state_machine.mode,
                rodas=rodas,
                imu=self.last_imu,
                visao=self.last_vision,
                bateria=bateria,
                ts_ms=int(time.time() * 1000),
            )
