"""App de alto nível da empilhadeira, rodando no Raspberry Pi.

Backend assíncrono único (FastAPI + asyncio) com três tarefas concorrentes:
WebSocket Handler, Vision Loop e Serial Loop.

[ref: Seção 2 da AGENTS.md]
"""
