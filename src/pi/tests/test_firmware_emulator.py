"""Testes do emulador de firmware: PID, anti-windup, fim-de-curso, watchdog."""

import json
import time

from app import config
from app.comms.crc8 import crc8_hex
from app.sim.firmware_emulator import FirmwareEmulator, MotorModel, PidController


def _make_setpoint_frame(w_esq: float, w_dir: float, garfo: str = "parar") -> bytes:
    data = {"w_esq": w_esq, "w_dir": w_dir, "garfo": garfo}
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    checksum = crc8_hex(payload)
    return f"{payload.decode()}*{checksum}\n".encode()


class TestPidController:
    def test_converges_to_setpoint(self):
        """PID deve convergir ao setpoint com motor simples."""
        pid = PidController(20.0, 5.0, 1.0)
        pid.setpoint = 5.0
        motor = MotorModel()
        dt = 0.01

        for _ in range(2000):
            u = pid.update(motor.omega, dt)
            motor.step(u, dt)

        assert abs(motor.omega - 5.0) < 1.0

    def test_anti_windup(self):
        """Integral deve ser clamped a ±PID_INTEGRAL_LIMIT."""
        pid = PidController(20.0, 5.0, 1.0)
        pid.setpoint = 100.0
        dt = 0.01

        for _ in range(1000):
            pid.update(0.0, dt)

        assert pid.integral <= config.EMU_PID_INTEGRAL_LIMIT
        assert pid.integral >= -config.EMU_PID_INTEGRAL_LIMIT

    def test_reset(self):
        """reset() zera estado interno."""
        pid = PidController(20.0, 5.0, 1.0)
        pid.setpoint = 5.0
        pid.update(0.0, 0.01)
        pid.reset()
        assert pid.setpoint == 0.0
        assert pid.integral == 0.0
        assert pid.prev_error == 0.0


class TestMotorModel:
    def test_saturation(self):
        """Motor não deve exceder MAX_OMEGA."""
        motor = MotorModel()
        for _ in range(1000):
            motor.step(1000.0, 0.01)
        assert motor.omega <= config.EMU_MAX_OMEGA + 0.1

    def test_responds_to_input(self):
        """Motor com u>0 deve eventualmente girar."""
        motor = MotorModel()
        for _ in range(100):
            motor.step(128.0, 0.01)
        assert motor.omega > 0


class TestFirmwareEmulator:
    def test_receives_setpoint(self):
        """Emulador aceita quadro de setpoint com CRC válido."""
        emu = FirmwareEmulator()
        frame = _make_setpoint_frame(5.0, 5.0)
        emu.receive_setpoint_frame(frame)
        assert emu.setpoint_valid
        assert abs(emu.setpoint_w_esq - 5.0) < 0.01

    def test_rejects_bad_crc(self):
        """Emulador rejeita quadro com CRC inválido."""
        emu = FirmwareEmulator()
        frame = _make_setpoint_frame(5.0, 5.0)
        bad = frame.replace(frame[-4:-2], b"ff")
        emu.receive_setpoint_frame(bad)
        assert not emu.setpoint_valid

    def test_generates_sensors_frame(self):
        """Emulador gera quadro de sensores com CRC válido."""
        emu = FirmwareEmulator()
        frame = emu.generate_sensors_frame()
        assert frame.endswith(b"\n")
        assert b"*" in frame

        text = frame.decode().strip()
        payload_str, checksum = text.rsplit("*", 1)
        assert crc8_hex(payload_str.encode()) == checksum

    def test_pid_converges(self):
        """Emulador com setpoint aplicado converge."""
        emu = FirmwareEmulator()
        frame = _make_setpoint_frame(5.0, 5.0)

        for _ in range(500):
            emu.receive_setpoint_frame(frame)
            emu.step(0.05)

        assert abs(emu.measured_esq - 5.0) < 2.0
        assert abs(emu.measured_dir - 5.0) < 2.0

    def test_watchdog_stops_motors(self):
        """Após timeout sem setpoint, motores devem parar."""
        emu = FirmwareEmulator()
        frame = _make_setpoint_frame(5.0, 5.0)
        emu.receive_setpoint_frame(frame)

        for _ in range(100):
            emu.step(0.01)

        time.sleep(0.25)
        emu.step(0.01)

        assert not emu.setpoint_valid

    def test_fork_limit_top(self):
        """Garfo não ultrapassa o limite superior."""
        emu = FirmwareEmulator()
        frame = _make_setpoint_frame(0.0, 0.0, "subir")

        for _ in range(1000):
            emu.receive_setpoint_frame(frame)
            emu.step(0.05)

        assert emu.fork_height <= config.EMU_FORK_MAX_HEIGHT
        assert emu.fork_at_top()

    def test_fork_limit_bottom(self):
        """Garfo não vai abaixo do limite inferior."""
        emu = FirmwareEmulator()
        frame = _make_setpoint_frame(0.0, 0.0, "descer")

        for _ in range(1000):
            emu.receive_setpoint_frame(frame)
            emu.step(0.05)

        assert emu.fork_height >= config.EMU_FORK_MIN_HEIGHT
        assert emu.fork_at_bottom()

    def test_serial_drop(self):
        """Com serial drop injetado, setpoint não é aceito."""
        emu = FirmwareEmulator()
        emu.set_serial_drop(True)
        frame = _make_setpoint_frame(5.0, 5.0)
        emu.receive_setpoint_frame(frame)
        assert not emu.setpoint_valid
