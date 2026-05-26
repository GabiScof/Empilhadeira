"""Ponto de entrada do backend do Pi: cria as 3 tarefas asyncio concorrentes.

Backend assíncrono único (FastAPI + asyncio). Sobe três tarefas que compartilham
`SharedState`:
- WebSocket Handler (comando/telemetria com o frontend)
- Vision Loop (AprilTag → pose)
- Serial Loop (setpoint/sensores com o ESP32)

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations


def create_app() -> object:
    """Cria a aplicação FastAPI e registra as rotas/WebSocket.

    Returns:
        Instância de FastAPI (tipada como object enquanto stub).
    """
    raise NotImplementedError


async def run() -> None:
    """Sobe as três tarefas asyncio concorrentes e aguarda até o encerramento.

    Cria o estado compartilhado e agenda WebSocket Handler, Vision Loop e Serial
    Loop com asyncio. Em caso de cancelamento, leva o sistema a estado seguro.
    """
    raise NotImplementedError


def main() -> None:
    """Entrada de linha de comando: roda o servidor (uvicorn) com `run()`."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
