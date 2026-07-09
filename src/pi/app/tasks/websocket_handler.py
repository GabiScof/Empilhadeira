"""Tarefa WebSocket: recebe comandos (1) e envia telemetria (2).

Endpoint /ws do FastAPI. O handler **não** calcula setpoint — isso é
responsabilidade do `control_loop` (malha fechada a 20 Hz, independente da cadência
do operador). Aqui só registramos a intenção do operador (modo/joystick/garfo) no
estado e reconhecemos (`acknowledge`) a saída de uma parada de segurança.
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app import config
from app.models import Command, Mode
from app.state import SharedState

logger = logging.getLogger(__name__)


async def websocket_endpoint(websocket: WebSocket, state: SharedState) -> None:
    """Handler de uma conexão WebSocket de operador.

    Args:
        websocket: conexão WebSocket do FastAPI.
        state: estado compartilhado.
    """
    await websocket.accept()
    logger.info("WebSocket conectado: %s", websocket.client)

    send_task = asyncio.create_task(_telemetry_sender(websocket, state))

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                command = Command.model_validate_json(raw)
            except ValidationError:
                logger.warning("Comando inválido descartado")
                continue

            await state.update_command(command)
            current_time_ms = int(time.time() * 1000)
            state.state_machine.update_command_time(current_time_ms)

            # Comando de modo do operador é a ação explícita que libera o latch de
            # uma parada de segurança (o frontend só envia comando ao interagir).
            if command.modo in (Mode.MANUAL, Mode.AUTOMATICO):
                state.state_machine.acknowledge()

    except WebSocketDisconnect:
        logger.info("WebSocket desconectado: %s", websocket.client)
    except asyncio.CancelledError:
        pass
    finally:
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass

        # Conexão caiu: estado seguro. Limpa a intenção do operador para o
        # control_loop não continuar dirigindo com um comando obsoleto.
        state.state_machine.force_stop(reason="ws_disconnect")
        await state.clear_command()
        logger.info("WS desconectado → PARADO (intenção do operador limpa)")


async def _telemetry_sender(websocket: WebSocket, state: SharedState) -> None:
    """Envia telemetria ao frontend @20 Hz."""
    interval = 1.0 / config.TELEMETRY_HZ

    try:
        while True:
            telemetry = await state.snapshot_telemetry()
            await websocket.send_text(telemetry.model_dump_json())
            await asyncio.sleep(interval)
    except (asyncio.CancelledError, WebSocketDisconnect):
        pass
