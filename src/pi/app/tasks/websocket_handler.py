"""Tarefa WebSocket: recebe comandos do frontend e envia telemetria @20 Hz.

Responsabilidades:
- Decodificar comandos (contrato 1) e atualizar o estado compartilhado.
- Enviar telemetria (contrato 2) na taxa de `TELEMETRY_HZ`.
- **Watchdog de comando**: se nenhum comando chegar em `COMMAND_WATCHDOG_MS`
  durante o modo MANUAL com o robô em movimento, forçar PARADO. [ref: Seção 4 e 7]

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

from app.state import SharedState


async def websocket_handler(state: SharedState) -> None:
    """Loop da tarefa de WebSocket (comando in / telemetria out).

    Args:
        state: estado compartilhado entre as tarefas.
    """
    raise NotImplementedError
