"""Estrutura de testes do protocolo serial (sem lógica real).

Verificará round-trip encode/decode e descarte de quadros com CRC inválido.
[ref: Seção 6, 7 e 11 da AGENTS.md]
"""

import pytest


@pytest.mark.skip(reason="TODO: implementar após encode_setpoint/decode_sensors.")
def test_setpoint_roundtrip() -> None:
    """encode_setpoint → decode deve preservar os campos do setpoint."""
    raise NotImplementedError


@pytest.mark.skip(reason="TODO: implementar após validação de CRC.")
def test_decode_rejects_bad_crc() -> None:
    """decode_sensors deve levantar ValueError quando o CRC não bate."""
    raise NotImplementedError
