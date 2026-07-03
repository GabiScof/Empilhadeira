"""Testes do protocolo serial: round-trip, CRC, ressincronização e schema."""

import json

from app.comms.crc8 import crc8_hex
from app.comms.protocol import (
    SensorsFrameDecoder,
    decode_sensors,
    encode_setpoint,
)
from app.models import ForkCommand, Setpoint


def _make_sensors_frame(data: dict) -> bytes:
    """Helper: monta quadro de sensores válido."""
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    checksum = crc8_hex(payload).encode("ascii")
    return payload + b"*" + checksum + b"\n"


VALID_SENSORS = {
    "enc": {"esq": 1.5, "dir": 2.0},
    "mpu": {"ax": 0.1, "ay": 0.2, "az": 9.8, "gx": 0.0, "gy": 0.0, "gz": 0.0, "temp_c": 25.0},
    "bms": None,
}


def test_setpoint_encode_format():
    """encode_setpoint gera quadro <json>*<crc8>\\n."""
    sp = Setpoint(w_esq=1.0, w_dir=2.0, garfo=ForkCommand.PARAR)
    frame = encode_setpoint(sp)

    assert frame.endswith(b"\n")
    assert b"*" in frame

    parts = frame.rstrip(b"\n").rsplit(b"*", 1)
    assert len(parts) == 2
    payload, checksum = parts
    assert len(checksum) == 2
    assert crc8_hex(payload) == checksum.decode("ascii")


def test_setpoint_roundtrip():
    """encode → decode preserva campos do setpoint."""
    sp = Setpoint(w_esq=5.5, w_dir=-3.0, garfo=ForkCommand.SUBIR)
    frame = encode_setpoint(sp)

    payload_part = frame.rstrip(b"\n").rsplit(b"*", 1)[0]
    data = json.loads(payload_part)
    assert abs(data["w_esq"] - 5.5) < 0.01
    assert abs(data["w_dir"] - (-3.0)) < 0.01
    assert data["garfo"] == "subir"


def test_decode_sensors_valid():
    """decode_sensors aceita quadro válido."""
    frame = _make_sensors_frame(VALID_SENSORS)
    sensors = decode_sensors(frame)

    assert sensors is not None
    assert abs(sensors.enc.esq - 1.5) < 0.01
    assert abs(sensors.enc.dir - 2.0) < 0.01
    assert sensors.bms is None


def test_decode_sensors_bad_crc():
    """decode_sensors rejeita quadro com CRC errado."""
    frame = _make_sensors_frame(VALID_SENSORS)
    corrupted = frame.replace(frame[-4:-2], b"ff")
    sensors = decode_sensors(corrupted)
    assert sensors is None


def test_decode_sensors_no_separator():
    """decode_sensors rejeita quadro sem '*'."""
    sensors = decode_sensors(b'{"enc":{"esq":0,"dir":0}}00\n')
    assert sensors is None


def test_decode_sensors_invalid_json():
    """decode_sensors rejeita JSON malformado."""
    payload = b"not json at all"
    checksum = crc8_hex(payload).encode("ascii")
    frame = payload + b"*" + checksum + b"\n"
    sensors = decode_sensors(frame)
    assert sensors is None


def test_decode_sensors_invalid_schema():
    """decode_sensors rejeita JSON que não conforma ao schema Sensors."""
    data = {"wrong_field": 123}
    frame = _make_sensors_frame(data)
    sensors = decode_sensors(frame)
    assert sensors is None


def test_sensors_frame_decoder_resync():
    """SensorsFrameDecoder ressincroniza no '\\n' após lixo."""
    decoder = SensorsFrameDecoder()

    garbage = b"lixo lixo lixo\n"
    valid = _make_sensors_frame(VALID_SENSORS)

    results = decoder.feed(garbage + valid)
    assert len(results) == 1
    assert abs(results[0].enc.esq - 1.5) < 0.01


def test_sensors_frame_decoder_multiple():
    """SensorsFrameDecoder decodifica múltiplos quadros concatenados."""
    decoder = SensorsFrameDecoder()

    frame1 = _make_sensors_frame(VALID_SENSORS)
    data2 = {**VALID_SENSORS, "enc": {"esq": 3.0, "dir": 4.0}}
    frame2 = _make_sensors_frame(data2)

    results = decoder.feed(frame1 + frame2)
    assert len(results) == 2
    assert abs(results[1].enc.esq - 3.0) < 0.01
