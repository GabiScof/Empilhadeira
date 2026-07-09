"""Produtor de telemetria FAKE — substituto temporário de Vision Loop + Serial Loop.

Escreve, a 20 Hz, valores plausíveis nos campos de SharedState usados pelos loops reais.
"""

from __future__ import annotations

import asyncio
import math

from app.config import TELEMETRY_HZ
from app.models import Encoders, ImuAngles, MpuRaw, Sensors
from app.state import SharedState


async def fake_telemetry_producer(state: SharedState) -> None:
    """Publica sensores e IMU sintéticos no SharedState a TELEMETRY_HZ.

    Args:
        state: estado compartilhado que será lido pelo WS Handler.
    """
    interval = 1.0 / TELEMETRY_HZ
    t = 0.0

    while True:
        t += interval

        enc = Encoders(
            esq=round(math.sin(t) * 2.0, 4),
            dir=round(math.sin(t + 0.4) * 2.0, 4),
        )
        # MPU cru: apenas gravidade em az; Kalman real calcularia roll/pitch disso.
        mpu = MpuRaw(ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=0.0, temp_c=25.0)
        await state.update_sensors(Sensors(enc=enc, mpu=mpu, bms=None))

        # roll/pitch filtrados que o Kalman produziria (aqui é apenas senóide lenta)
        await state.update_imu(
            ImuAngles(
                roll=round(math.sin(t * 0.3) * 5.0, 2),
                pitch=round(math.cos(t * 0.2) * 3.0, 2),
            )
        )

        await asyncio.sleep(interval)
