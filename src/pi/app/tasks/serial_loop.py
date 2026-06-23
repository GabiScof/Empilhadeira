"""Tarefa serial: troca contratos (3)/(4) com ESP32 ou emulador.

Em SIM: usa FirmwareEmulator + EKF prediction.
Em REAL: pyserial-asyncio para UART + EKF prediction.

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import logging
import math
import time

from app import config
from app.comms.protocol import encode_setpoint
from app.state import SharedState

logger = logging.getLogger(__name__)


def _feed_ekf(state: SharedState, sensors, dt: float) -> None:
    """Alimenta o EKF com dados de encoder + giroscópio."""
    w_left = sensors.enc.esq
    w_right = sensors.enc.dir
    gyro_z_dps = sensors.mpu.gz
    gyro_z_rads = math.radians(gyro_z_dps)

    state.ekf.predict(
        w_left=w_left,
        w_right=w_right,
        gyro_z_rads=gyro_z_rads,
        dt=dt,
        wheel_radius_m=config.WHEEL_RADIUS_M,
        wheelbase_m=config.WHEELBASE_M,
    )


async def serial_loop_sim(state: SharedState) -> None:
    """Loop serial em modo simulação.

    Lê ``state.sim_emulator`` a cada tick para suportar hot-swap de mapa.
    """
    from app.sim.firmware_emulator import FirmwareEmulator

    logger.info("Serial loop (SIM) iniciado")
    interval = 1.0 / config.SERIAL_HZ
    last_time = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            dt = now - last_time
            last_time = now

            emulator = state.sim_emulator
            if not isinstance(emulator, FirmwareEmulator):
                await asyncio.sleep(interval)
                continue

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

                _feed_ekf(state, sensors, dt)

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Serial loop (SIM) cancelado")


async def serial_loop_real(state: SharedState, transport=None) -> None:
    """Loop serial em modo real, dirigindo um ``SerialTransport`` injetável.

    Args:
        state: estado compartilhado.
        transport: implementação de ``app.hardware.interfaces.SerialTransport``.
            Default: ``PySerialTransport`` (UART via pyserial-asyncio).
    """
    if transport is None:
        from app.comms.serial_transport import PySerialTransport

        transport = PySerialTransport()

    logger.info("Serial loop (REAL) iniciado — porta %s", config.SERIAL_PORT)
    interval = 1.0 / config.SERIAL_HZ

    await transport.open()
    last_time = time.monotonic()
    lost_frames = 0  # ciclos consecutivos sem sensores (watchdog serial)

    try:
        while True:
            now = time.monotonic()
            dt = now - last_time
            last_time = now

            async with state.lock:
                setpoint = state.current_setpoint

            await transport.send_setpoint(setpoint)

            frames = await transport.read_sensors(interval)
            if frames:
                lost_frames = 0
                for sensors in frames:
                    await state.update_sensors(sensors)
                    imu = state.kalman.update(sensors.mpu, dt)
                    await state.update_imu(imu)
                    _feed_ekf(state, sensors, dt)
            else:
                # Watchdog serial: se a UART parar de entregar sensores por
                # SERIAL_LOST_FRAMES ciclos (~250 ms @20 Hz), força PARADO no Pi.
                # Defesa em profundidade sobre o SETPOINT_TIMEOUT_MS do firmware,
                # que já zera os motores localmente. [ref: Seção 7]
                lost_frames += 1
                if lost_frames >= config.SERIAL_LOST_FRAMES:
                    if lost_frames == config.SERIAL_LOST_FRAMES:
                        logger.warning(
                            "Watchdog serial: %d ciclos sem sensores — forçando PARADO",
                            lost_frames,
                        )
                    state.state_machine.force_stop(reason="serial_loss")

            await asyncio.sleep(max(0, interval - (time.monotonic() - now)))
    except asyncio.CancelledError:
        logger.info("Serial loop (REAL) cancelado")
    finally:
        await transport.close()
