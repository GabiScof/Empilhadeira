"""Tarefa serial: troca contratos (3)/(4) com ESP32 ou emulador.

Em modo real: pyserial-asyncio para UART.
Em modo SIM: usa FirmwareEmulator diretamente.

Aplica Kalman nos dados de MPU recebidos. Taxa: 20 Hz.

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import logging
import time

from app import config
from app.comms.protocol import SensorsFrameDecoder, encode_setpoint
from app.state import SharedState

logger = logging.getLogger(__name__)


async def serial_loop_sim(state: SharedState, emulator: object) -> None:
    """Loop serial em modo simulação (usa emulador em vez de UART).

    Args:
        state: estado compartilhado.
        emulator: FirmwareEmulator instance.
    """
    from app.sim.firmware_emulator import FirmwareEmulator

    if not isinstance(emulator, FirmwareEmulator):
        raise TypeError("emulator deve ser FirmwareEmulator")

    logger.info("Serial loop (SIM) iniciado")
    interval = 1.0 / config.SERIAL_HZ
    last_time = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            dt = now - last_time
            last_time = now

            async with state.lock:
                setpoint = state.current_setpoint

            frame = encode_setpoint(setpoint)
            emulator.receive_setpoint_frame(frame)

            emulator.step(dt)

            sensors_frame = emulator.generate_sensors_frame()
            from app.comms.protocol import decode_sensors

            sensors = decode_sensors(sensors_frame)
            if sensors is not None:
                await state.update_sensors(sensors)

                imu = state.kalman.update(sensors.mpu, dt)
                await state.update_imu(imu)

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Serial loop (SIM) cancelado")


async def serial_loop_real(state: SharedState) -> None:
    """Loop serial em modo real (UART com pyserial-asyncio).

    Args:
        state: estado compartilhado.
    """
    import serial_asyncio

    logger.info("Serial loop (REAL) iniciado — porta %s", config.SERIAL_PORT)
    interval = 1.0 / config.SERIAL_HZ
    decoder = SensorsFrameDecoder()

    reader, writer = await serial_asyncio.open_serial_connection(
        url=config.SERIAL_PORT,
        baudrate=config.SERIAL_BAUDRATE,
    )

    last_time = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            dt = now - last_time
            last_time = now

            async with state.lock:
                setpoint = state.current_setpoint

            frame = encode_setpoint(setpoint)
            writer.write(frame)
            await writer.drain()

            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=interval)
                if data:
                    sensors_list = decoder.feed(data)
                    for sensors in sensors_list:
                        await state.update_sensors(sensors)
                        imu = state.kalman.update(sensors.mpu, dt)
                        await state.update_imu(imu)
            except TimeoutError:
                pass

            await asyncio.sleep(max(0, interval - (time.monotonic() - now)))
    except asyncio.CancelledError:
        logger.info("Serial loop (REAL) cancelado")
    finally:
        writer.close()
