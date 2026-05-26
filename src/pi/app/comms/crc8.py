"""CRC-8 do framing serial.

Calcula o CRC-8 do payload JSON (bytes UTF-8 antes do `*`). O algoritmo (polinômio
e valor inicial) deve ser **idêntico** ao do firmware (`firmware/src/protocol.*`).

A escolha do polinômio/init é `TODO(equipe)` — fixar antes da implementação para os
dois lados baterem. [ref: Seção 6 e 7 da AGENTS.md]
"""

from __future__ import annotations

# TODO(equipe): fixar polinômio e valor inicial do CRC-8 (idênticos no firmware).
CRC8_POLYNOMIAL: int | None = None
CRC8_INIT: int | None = None


def crc8(data: bytes) -> int:
    """Calcula o CRC-8 de uma sequência de bytes.

    Args:
        data: payload (bytes UTF-8 do JSON compacto, antes do `*`).

    Returns:
        Valor do CRC-8 (0–255).
    """
    raise NotImplementedError


def crc8_hex(data: bytes) -> str:
    """Calcula o CRC-8 e formata em 2 dígitos hexadecimais minúsculos.

    Args:
        data: payload (bytes UTF-8 do JSON compacto).

    Returns:
        CRC-8 como string de 2 caracteres hex (ex.: "a3").
    """
    raise NotImplementedError
