"""Ponto de entrada do backend do Pi: cria a app FastAPI e as tarefas asyncio.

Backend assíncrono único (FastAPI + asyncio). Ao iniciar o servidor:
  1. fake_telemetry_producer escreve sensores sintéticos no SharedState @20 Hz.
     # SCAFFOLDING: substituir por vision_loop + serial_loop quando prontos.
  2. O endpoint /ws aceita conexões WebSocket do frontend e lança websocket_handler
     por conexão, que gerencia comando (contrato 1) e telemetria (contrato 2).

Como subir:
    uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
    # Para carregar o .env da raiz do monorepo:
    uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --env-file ../.env

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from app.config import WS_HOST, WS_PORT
from app.state import SharedState
from app.tasks.fake_telemetry_producer import fake_telemetry_producer  # SCAFFOLDING
from app.tasks.websocket_handler import websocket_handler

_log = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Estado compartilhado único para o processo; as três tarefas asyncio lêem/escrevem aqui.
_state = SharedState()


@asynccontextmanager
async def _lifespan(app: FastAPI):  # app é injetado pelo FastAPI; não usado no corpo
    """Ciclo de vida da aplicação: sobe tarefas de fundo e garante encerramento limpo."""
    tasks = [
        asyncio.create_task(fake_telemetry_producer(_state), name="fake-producer"),
        # SCAFFOLDING: substituir as duas linhas abaixo quando os loops reais entrarem:
        # asyncio.create_task(vision_loop(_state), name="vision-loop"),
        # asyncio.create_task(serial_loop(_state), name="serial-loop"),
    ]
    _log.info("Tarefas de fundo iniciadas: %s", [t.get_name() for t in tasks])
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        _log.info("Tarefas de fundo encerradas.")


def create_app() -> FastAPI:
    """Cria e configura a instância FastAPI (modo factory para uvicorn --factory).

    Returns:
        Instância de FastAPI com endpoint /ws registrado e lifespan configurado.
    """
    app = FastAPI(title="Empilhadeira Pi", lifespan=_lifespan)

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket_handler(websocket, _state)

    return app


async def run() -> None:
    """Sobe o servidor uvicorn programaticamente (alternativa ao CLI)."""
    import uvicorn

    config = uvicorn.Config(create_app(), host=WS_HOST, port=WS_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """Entrada de linha de comando: inicia o servidor de forma bloqueante."""
    import uvicorn

    uvicorn.run(create_app(), host=WS_HOST, port=WS_PORT, log_level="info")


if __name__ == "__main__":
    main()
