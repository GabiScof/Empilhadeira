"""Estrutura de testes do CRC-8 (sem lógica real — casos marcados).

Os casos só serão preenchidos quando a equipe fixar o polinômio/init do CRC-8
(ver app/comms/crc8.py). [ref: Seção 11 da AGENTS.md — não escrever testes com lógica real]
"""

import pytest


@pytest.mark.skip(reason="TODO(equipe): fixar polinômio/init do CRC-8 antes de testar.")
def test_crc8_known_vector() -> None:
    """CRC-8 de um vetor conhecido deve bater com o valor de referência."""
    raise NotImplementedError


@pytest.mark.skip(reason="TODO: implementar após crc8/crc8_hex.")
def test_crc8_hex_format() -> None:
    """crc8_hex deve devolver exatamente 2 dígitos hex minúsculos."""
    raise NotImplementedError
