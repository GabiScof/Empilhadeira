"""Estrutura de testes do protocolo serial (sem lógica real).

Verificará round-trip encode/decode e descarte de quadros com CRC inválido.
[ref: Seção 6, 7 e 11 da AGENTS.md]
"""

import pytest
from app.comms.crc8 import crc8, crc8_hex
from app.comms.protocol import encode_setpoint, decode_sensors, SensorsFrameDecoder
from app.models import Setpoint, Sensors


@pytest.mark.skip(reason="TODO: implementar após encode_setpoint/decode_sensors.")
def test_setpoint_roundtrip() -> None:
    """encode_setpoint → decode deve preservar os campos do setpoint."""
    raise NotImplementedError


@pytest.mark.skip(reason="TODO: implementar após validação de CRC.")
def test_decode_rejects_bad_crc() -> None:
    """decode_sensors deve levantar ValueError quando o CRC não bate."""
    raise NotImplementedError

# ── CRC ──────────────────────────────────────────────────────────────
class TestCrc8:
    def test_known_value(self):
        payload = b'{"w_esq":1.5,"w_dir":1.5,"garfo":"parar"}'
        assert crc8_hex(payload) == "6e"

    def test_empty(self):
        assert crc8(b"") == 0x00

    def test_sensors_frame(self):
        payload = b'{"enc":{"esq":1.5,"dir":1.5},"mpu":{"ax":0,"ay":0,"az":9.81,"gx":0,"gy":0,"gz":0,"temp_c":25},"bms":null}'
        assert crc8_hex(payload) == "d5"

# ── encode_setpoint ───────────────────────────────────────────────────
class TestEncodeSetpoint:
    def test_frame_format(self):
        sp = Setpoint(w_esq=1.5, w_dir=1.5, garfo="parar")
        frame = encode_setpoint(sp)
        assert frame.endswith(b"\n")
        assert b"*" in frame

    def test_known_crc(self):
        sp = Setpoint(w_esq=1.5, w_dir=1.5, garfo="parar")
        assert encode_setpoint(sp) == b'{"w_esq":1.5,"w_dir":1.5,"garfo":"parar"}*6e\n'

    def test_parado(self):
        sp = Setpoint(w_esq=0.0, w_dir=0.0, garfo="parar")
        assert encode_setpoint(sp) == b'{"w_esq":0.0,"w_dir":0.0,"garfo":"parar"}*5e\n'

    def test_giro_subir(self):
        sp = Setpoint(w_esq=-1.0, w_dir=1.0, garfo="subir")
        assert encode_setpoint(sp) == b'{"w_esq":-1.0,"w_dir":1.0,"garfo":"subir"}*df\n'

# ── decode_sensors ────────────────────────────────────────────────────
class TestDecodeSensors:
    VALID = b'{"enc":{"esq":1.5,"dir":1.5},"mpu":{"ax":0,"ay":0,"az":9.81,"gx":0,"gy":0,"gz":0,"temp_c":25},"bms":null}*d5\n'

    def test_valid_frame(self):
        s = decode_sensors(self.VALID)
        assert s is not None
        assert s.enc.esq == 1.5
        assert s.enc.dir == 1.5
        assert s.mpu.az  == pytest.approx(9.81)
        assert s.bms is None

    def test_crc_errado(self):
        bad = self.VALID.replace(b"*d5", b"*ff")
        assert decode_sensors(bad) is None

    def test_sem_separador(self):
        assert decode_sensors(b'{"enc":{}}\n') is None

    def test_payload_vazio(self):
        assert decode_sensors(b"*d5\n") is None

    def test_json_invalido(self):
        assert decode_sensors(b"nao_e_json*zz\n") is None

# ── SensorsFrameDecoder (incremental) ─────────────────────────────────
class TestSensorsFrameDecoder:
    FRAME = b'{"enc":{"esq":1.5,"dir":1.5},"mpu":{"ax":0,"ay":0,"az":9.81,"gx":0,"gy":0,"gz":0,"temp_c":25},"bms":null}*d5\n'

    def test_frame_inteiro(self):
        dec = SensorsFrameDecoder()
        result = dec.feed(self.FRAME)
        assert len(result) == 1
        assert result[0].enc.esq == 1.5

    def test_frame_fragmentado(self):
        """Simula bytes chegando pela UART de 1 em 1."""
        dec = SensorsFrameDecoder()
        result = []
        for byte in self.FRAME:
            result.extend(dec.feed(bytes([byte])))
        assert len(result) == 1

    def test_dois_frames_seguidos(self):
        dec = SensorsFrameDecoder()
        result = dec.feed(self.FRAME + self.FRAME)
        assert len(result) == 2

    def test_frame_corrompido_seguido_de_valido(self):
        """Frame ruim deve ser descartado; o próximo válido deve passar."""
        bad = b'lixo_corrompido*ff\n'
        dec = SensorsFrameDecoder()
        result = dec.feed(bad + self.FRAME)
        assert len(result) == 1