"""CRC-8/MAXIM usado no framing serial Pi <-> ESP32.

O CRC e calculado sobre os bytes UTF-8 do JSON compacto, antes do separador `*`.
Esta variante deve ser identica ao firmware:

- CRC-8/MAXIM (Dallas/1-Wire)
- Polinomio normal 0x31, refletido 0x8C
- Init 0x00, RefIn true, RefOut true, XorOut 0x00
"""

from __future__ import annotations

CRC8_POLYNOMIAL: int = 0x31
CRC8_REFLECTED_POLYNOMIAL: int = 0x8C
CRC8_INIT: int = 0x00
CRC8_XOR_OUT: int = 0x00


def crc8(data: bytes) -> int:
    """Calcula CRC-8/MAXIM de uma sequencia de bytes.

    Args:
        data: payload JSON em UTF-8, sem `*`, sem CRC e sem `\\n`.

    Returns:
        Valor do CRC-8 no intervalo 0..255.
    """
    crc = CRC8_INIT
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x01:
                crc = (crc >> 1) ^ CRC8_REFLECTED_POLYNOMIAL
            else:
                crc >>= 1
            crc &= 0xFF
    return crc ^ CRC8_XOR_OUT


def crc8_hex(data: bytes) -> str:
    """Calcula CRC-8/MAXIM e formata em 2 digitos hexadecimais minusculos.

    Args:
        data: payload JSON em UTF-8, sem `*`, sem CRC e sem `\\n`.

    Returns:
        CRC em hex minusculo, sempre com 2 caracteres.
    """
    return f"{crc8(data):02x}"
