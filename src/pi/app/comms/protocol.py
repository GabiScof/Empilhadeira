"""Protocolo serial Pi <-> ESP32: JSON compacto + CRC8 + ``\\n``.

Este modulo implementa somente os contratos UART:

- Contrato (3): Pi -> ESP32, setpoint de rodas em rad/s e comando do garfo.
- Contrato (4): ESP32 -> Pi, sensores crus em unidades fixadas no contrato.

Framing serial:
    ``<json compacto>*<CRC8 em 2 digitos hex minusculos>\\n``

Na recepcao, o loop deve ressincronizar pelo terminador ``\\n``. Quadros com CRC,
JSON ou schema invalidos sao descartados retornando ``None``; isso evita derrubar a
tarefa serial por erro de parsing de um unico quadro.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from pydantic import ValidationError

from app.comms.crc8 import crc8_hex
from app.models import Sensors, Setpoint

FRAME_SEPARATOR = b"*"
FRAME_TERMINATOR = b"\n"
CHECKSUM_HEX_LEN = 2

# TODO(equipe): dimensionar um limite maximo de buffer serial se a integracao
# precisar proteger contra fluxo sem `\n`. None deixa o chamador decidir.
DEFAULT_MAX_BUFFER_BYTES: int | None = None


def encode_setpoint(setpoint: Setpoint) -> bytes:
    """Serializa contrato (3) em ``<json>*<crc8hex>\\n``.

    Args:
        setpoint: setpoint de roda esquerda/direita em rad/s e comando do garfo.

    Returns:
        Quadro pronto para escrita na UART, terminado em ``\\n``.
    """
    payload = _compact_json_bytes(setpoint.model_dump(mode="json"))
    checksum = crc8_hex(payload).encode("ascii")
    return payload + FRAME_SEPARATOR + checksum + FRAME_TERMINATOR


def decode_sensors(frame: bytes | bytearray | memoryview) -> Sensors | None:
    """Desserializa contrato (4) de um quadro ja separado por ``\\n``.

    Args:
        frame: quadro ``<json>*<crc8hex>`` com ou sem terminador ``\\n``.

    Returns:
        ``Sensors`` validado quando o CRC e o JSON batem; ``None`` quando o quadro
        deve ser descartado.
    """
    parsed = _validated_payload(bytes(frame))
    if parsed is None:
        return None

    try:
        return Sensors.model_validate_json(parsed)
    except ValidationError:
        return None


def decode_sensors_or_raise(frame: bytes | bytearray | memoryview) -> Sensors:
    """Versao diagnostica de ``decode_sensors`` que levanta ``ValueError``.

    O caminho normal do loop serial deve preferir ``decode_sensors`` para descartar
    quadros ruins sem derrubar a tarefa.
    """
    sensors = decode_sensors(frame)
    if sensors is None:
        raise ValueError("quadro de sensores invalido ou CRC incorreto")
    return sensors


class SensorsFrameDecoder:
    """Decoder incremental para bytes recebidos da UART.

    O metodo ``feed`` acumula bytes ate ``\\n``, tenta validar cada quadro completo e
    retorna apenas os pacotes ``Sensors`` validos. Quadros invalidos sao descartados
    integralmente, preservando a ressincronizacao no proximo ``\\n``.
    """

    def __init__(self, max_buffer_bytes: int | None = DEFAULT_MAX_BUFFER_BYTES) -> None:
        self._buffer = bytearray()
        self._max_buffer_bytes = max_buffer_bytes

    def feed(self, data: bytes | bytearray | memoryview) -> list[Sensors]:
        """Consome bytes de UART e devolve todos os quadros validos completos."""
        self._buffer.extend(bytes(data))
        self._trim_if_needed()

        decoded: list[Sensors] = []
        while True:
            try:
                newline_index = self._buffer.index(FRAME_TERMINATOR)
            except ValueError:
                break

            raw_frame = bytes(self._buffer[:newline_index])
            del self._buffer[: newline_index + len(FRAME_TERMINATOR)]

            sensors = decode_sensors(raw_frame)
            if sensors is not None:
                decoded.append(sensors)

        return decoded

    def pending_bytes(self) -> int:
        """Retorna quantos bytes ainda aguardam terminador ``\\n``."""
        return len(self._buffer)

    def clear(self) -> None:
        """Descarta bytes pendentes ate o proximo periodo de leitura."""
        self._buffer.clear()

    def _trim_if_needed(self) -> None:
        if self._max_buffer_bytes is None or len(self._buffer) <= self._max_buffer_bytes:
            return

        # Sem terminador, nao ha quadro recuperavel. O chamador define o limite
        # conforme a integracao serial real quando quiser essa protecao ativa.
        self._buffer.clear()


def iter_decoded_sensors(frames: Iterable[bytes]) -> list[Sensors]:
    """Valida uma sequencia de quadros ja separados e retorna apenas os validos."""
    decoded: list[Sensors] = []
    for frame in frames:
        sensors = decode_sensors(frame)
        if sensors is not None:
            decoded.append(sensors)
    return decoded


def _compact_json_bytes(data: object) -> bytes:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode(
        "utf-8"
    )


def _validated_payload(frame: bytes) -> bytes | None:
    normalized = frame.rstrip(b"\r\n")
    try:
        payload, checksum = normalized.rsplit(FRAME_SEPARATOR, 1)
    except ValueError:
        return None

    if not payload or len(checksum) != CHECKSUM_HEX_LEN:
        return None

    try:
        checksum_text = checksum.decode("ascii")
    except UnicodeDecodeError:
        return None

    if not _is_lower_hex_checksum(checksum_text):
        return None

    expected = crc8_hex(payload)
    if checksum_text != expected:
        return None

    return payload


def _is_lower_hex_checksum(value: str) -> bool:
    return len(value) == CHECKSUM_HEX_LEN and all(char in "0123456789abcdef" for char in value)
