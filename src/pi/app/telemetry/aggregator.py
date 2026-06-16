"""Agregador de telemetria — módulo reservado para uso futuro.

A montagem do contrato (2) vive em `SharedState.snapshot_telemetry` (state.py),
que é o único ponto lido pelo WebSocket Handler. Este módulo pode receber funções
auxiliares de pré-processamento de telemetria quando a lógica crescer, mas por
enquanto não exporta nada utilizável.

[ref: Seção 6 da AGENTS.md]
"""
