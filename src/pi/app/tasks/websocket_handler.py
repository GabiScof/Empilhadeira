"""Tarefa WebSocket: recebe comandos do frontend e envia telemetria @20 Hz.

Responsabilidades:
- Aceitar a conexão WebSocket e rodar dois sub-loops concorrentes:
  · _receive: lê frames do cliente, valida como Command (contrato 1) e atualiza
    o SharedState. Atualiza também o instante do último comando recebido.
  · _send: a cada 1/TELEMETRY_HZ s, lê um snapshot de telemetria do SharedState
    e envia ao cliente (contrato 2). Verifica o watchdog de comando.
- Watchdog: se COMMAND_TIMEOUT_MS ms se passarem sem nenhum comando, força PARADO
  independentemente do modo atual (conservador em qualquer modo). [ref: Seção 7]
- Na desconexão (normal ou por queda de rede): força PARADO no finally.

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.config import COMMAND_TIMEOUT_MS, TELEMETRY_HZ
from app.models import Command, Mode
from app.state import SharedState

_log = logging.getLogger(__name__)


async def websocket_handler(ws: WebSocket, state: SharedState) -> None:
    """Loop de comando/telemetria para uma conexão WebSocket.

    Aceita a conexão, lança _receive e _send como subtarefas asyncio e aguarda
    a primeira encerrar (desconexão ou erro). Garante PARADO ao sair.

    Args:
        ws: WebSocket da conexão FastAPI.
        state: estado compartilhado entre as tarefas.
    """
    await ws.accept()
    _log.info("[WS] cliente conectado: %s", ws.client)

    loop = asyncio.get_running_loop()
    last_cmd_time: float = loop.time()
    interval: float = 1.0 / TELEMETRY_HZ

    async def _receive() -> None:
        nonlocal last_cmd_time
        async for text in ws.iter_text():
            try:
                cmd = Command.model_validate_json(text)
                _log.info("[WS] comando recebido: %s", cmd.model_dump())
                print("Comando recebido:", cmd.model_dump())
                state.update_command(cmd)
                last_cmd_time = loop.time()
            except ValidationError as exc:
                _log.warning("[WS] comando inválido ignorado: %s", exc)

    async def _send() -> None:
        while True:
            elapsed_ms = (loop.time() - last_cmd_time) * 1000
            if elapsed_ms > COMMAND_TIMEOUT_MS:
                state.set_mode(Mode.PARADO)
            payload = state.snapshot_telemetry()
            await ws.send_text(payload.model_dump_json())
            await asyncio.sleep(interval)

    receive_task = asyncio.create_task(_receive(), name="ws-receive")
    send_task = asyncio.create_task(_send(), name="ws-send")

    try:
        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        for t in done:
            exc = t.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                _log.error("[WS] exceção na tarefa: %s", exc)
    finally:
        state.set_mode(Mode.PARADO)
        _log.info("[WS] cliente desconectado; modo → PARADO")
