"""Transporte serial real (UART) — implementação de referência de ``SerialTransport``.

Envolve ``pyserial-asyncio`` e o enquadramento/CRC de ``app.comms.protocol``. A
equipe pode trocar por outra implementação do mesmo Protocol (ex.: outro barramento)
sem tocar na lógica — ``serial_loop_real`` aceita qualquer ``SerialTransport``.
"""

from __future__ import annotations

import asyncio

from app import config
from app.comms.protocol import SensorsFrameDecoder, encode_setpoint
from app.models import Sensors, Setpoint


class PySerialTransport:
    """``SerialTransport`` sobre UART via pyserial-asyncio."""

    def __init__(self, port: str | None = None, baudrate: int | None = None) -> None:
        self._port = port or config.SERIAL_PORT
        self._baudrate = baudrate or config.SERIAL_BAUDRATE
        self._reader = None
        self._writer = None
        self._decoder = SensorsFrameDecoder()

    async def open(self) -> None:
        if self._writer is not None:
            return
        import serial_asyncio

        self._reader, self._writer = await serial_asyncio.open_serial_connection(
            url=self._port, baudrate=self._baudrate
        )

    async def send_setpoint(self, setpoint: Setpoint) -> None:
        if self._writer is None:
            raise RuntimeError("Transporte serial não foi aberto (chame open()).")
        self._writer.write(encode_setpoint(setpoint))
        await self._writer.drain()

    async def read_sensors(self, timeout_s: float) -> list[Sensors]:
        if self._reader is None:
            return []
        try:
            data = await asyncio.wait_for(self._reader.read(1024), timeout=timeout_s)
        except (TimeoutError, asyncio.TimeoutError):
            return []
        if not data:
            return []
        return self._decoder.feed(data)

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
            self._reader = None
