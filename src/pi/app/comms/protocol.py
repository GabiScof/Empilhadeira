"""Protocolo serial Pi ↔ ESP32: framing JSON + CRC8 + \\n.

Framing (ver docs/serial-protocol.md):
    <json compacto>*<CRC8 em 2 dígitos hex>\\n

Na **recepção**, ressincroniza no `\\n`, valida o CRC e **descarta** quadros com CRC
inválido. Serializa o setpoint (contrato 3) e desserializa os sensores (contrato 4).

[ref: Seção 6 e 7 da AGENTS.md]
"""

from __future__ import annotations

from app.models import Sensors, Setpoint


def encode_setpoint(setpoint: Setpoint) -> bytes:
    """Serializa um setpoint no quadro `<json>*<crc8hex>\\n`.

    Args:
        setpoint: contrato (3) a enviar ao ESP32.

    Returns:
        Quadro pronto para escrita na UART (bytes, terminado em \\n).
    """
    raise NotImplementedError


def decode_sensors(frame: bytes) -> Sensors:
    """Desserializa um quadro de sensores recebido do ESP32.

    Args:
        frame: quadro `<json>*<crc8hex>` (sem o \\n terminador).

    Returns:
        Sensors validado (contrato 4).

    Raises:
        ValueError: se o CRC não bater ou o JSON for inválido.
    """
    raise NotImplementedError
