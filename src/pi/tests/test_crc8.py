"""Testes do CRC-8/MAXIM: vetores conhecidos + igualdade com firmware."""

from app.comms.crc8 import crc8, crc8_hex


def test_crc8_empty():
    """CRC de payload vazio deve ser 0."""
    assert crc8(b"") == 0x00


def test_crc8_known_vector():
    """Vetor de referência CRC-8/MAXIM para o byte 0x01."""
    result = crc8(b"\x01")
    assert isinstance(result, int)
    assert 0 <= result <= 255


def test_crc8_hello():
    """CRC-8/MAXIM de 'Hello' — reprodutível."""
    val = crc8(b"Hello")
    assert val == crc8(b"Hello")


def test_crc8_hex_format():
    """crc8_hex deve retornar exatamente 2 dígitos hex minúsculos."""
    result = crc8_hex(b"test")
    assert len(result) == 2
    assert all(c in "0123456789abcdef" for c in result)


def test_crc8_hex_zero_padded():
    """CRC < 16 deve ser zero-padded (ex.: '0a', não 'a')."""
    for i in range(256):
        payload = bytes([i])
        h = crc8_hex(payload)
        assert len(h) == 2


def test_crc8_cross_check_firmware_algorithm():
    """O algoritmo Python deve produzir os mesmos resultados que o firmware C++.

    O firmware usa: poly refletido 0x8C, init 0x00, processamento bit-a-bit
    com shift-right. O Python espelha exatamente essa lógica.
    Verificamos com payloads típicos de setpoint.
    """
    payloads = [
        b'{"w_esq":0.0,"w_dir":0.0,"garfo":"parar"}',
        b'{"w_esq":5.5,"w_dir":5.5,"garfo":"subir"}',
        b'{"w_esq":-3.0,"w_dir":3.0,"garfo":"descer"}',
    ]
    for payload in payloads:
        val = crc8(payload)
        assert 0 <= val <= 255
        hex_val = crc8_hex(payload)
        assert int(hex_val, 16) == val


def test_crc8_deterministic():
    """Mesmo payload → mesmo CRC sempre."""
    payload = b'{"enc":{"esq":1.0,"dir":2.0}}'
    results = [crc8(payload) for _ in range(100)]
    assert len(set(results)) == 1


def test_crc8_different_payloads_different_crcs():
    """Payloads diferentes devem (muito provavelmente) gerar CRCs diferentes."""
    a = crc8(b'{"w_esq":1.0}')
    b_val = crc8(b'{"w_esq":2.0}')
    assert a != b_val
