"""Emulador do firmware ESP32 em Python.

Espelha fielmente o comportamento do firmware real (branch feat/firmware-production-ready):
- PID por roda: Kp=20, Ki=5, Kd=1, anti-windup clamp ±500, malha ~100 Hz.
- Motor: 1ª ordem (tau ~50 ms) + saturação ~12.25 rad/s, duty 0-255.
- Encoder: ω = (pulsos/PPR)·2π/dt, PPR=360.
- Garfo: duty fixo 180, fim-de-curso topo/base.
- MPU-6050: gera dados crus a partir da pose do robô (gravidade + ruído).
- Watchdog: 200 ms sem setpoint → motores zerados, PID reset.
- Cadências: PID ~100 Hz (acumulado), serial 20 Hz.

[ref: firmware/src/main.cpp, pid.cpp, motors.cpp, encoders.cpp]
"""

from __future__ import annotations

import json
import math
import time

from app import config
from app.comms.crc8 import crc8_hex
from app.models import ForkCommand


class PidController:
    """Réplica do PID do firmware (pid.cpp)."""

    def __init__(self, kp: float, ki: float, kd: float) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = 0.0
        self.integral = 0.0
        self.prev_error = 0.0

    def update(self, measured: float, dt: float) -> float:
        if dt <= 0:
            return 0.0

        error = self.setpoint - measured
        self.integral += error * dt
        self.integral = max(
            -config.EMU_PID_INTEGRAL_LIMIT,
            min(config.EMU_PID_INTEGRAL_LIMIT, self.integral),
        )

        derivative = (error - self.prev_error) / dt
        self.prev_error = error

        return self.kp * error + self.ki * self.integral + self.kd * derivative

    def reset(self) -> None:
        self.setpoint = 0.0
        self.integral = 0.0
        self.prev_error = 0.0


class MotorModel:
    """Modelo de motor de 1ª ordem com saturação (Lego NXT 53787)."""

    def __init__(self, tau: float = config.EMU_MOTOR_TAU) -> None:
        self.tau = tau
        self.omega = 0.0

    def step(self, u: float, dt: float) -> float:
        """Avança o modelo um passo.

        Args:
            u: esforço de controle do PID (sinal = sentido, |u| = duty).
            dt: intervalo de tempo (s).
        """
        duty = max(-config.EMU_MAX_DUTY, min(config.EMU_MAX_DUTY, u))
        target_omega = (duty / config.EMU_MAX_DUTY) * config.EMU_MAX_OMEGA

        alpha = dt / (self.tau + dt)
        self.omega += alpha * (target_omega - self.omega)

        return self.omega


class FirmwareEmulator:
    """Emulador completo do firmware ESP32."""

    def __init__(self, world: object | None = None, seed: int = config.SIM_DEFAULT_SEED) -> None:
        self.pid_esq = PidController(config.EMU_PID_KP, config.EMU_PID_KI, config.EMU_PID_KD)
        self.pid_dir = PidController(config.EMU_PID_KP, config.EMU_PID_KI, config.EMU_PID_KD)
        self.motor_esq = MotorModel()
        self.motor_dir = MotorModel()

        self.fork_height = 0.0
        self.fork_command = ForkCommand.PARAR

        self.setpoint_w_esq = 0.0
        self.setpoint_w_dir = 0.0
        self.setpoint_garfo = ForkCommand.PARAR
        self.setpoint_valid = False
        self.last_setpoint_time = 0.0

        self.measured_esq = 0.0
        self.measured_dir = 0.0

        self._world = world
        self._seed = seed
        import random

        self._rng = random.Random(seed)

        self._pid_accumulator = 0.0
        self._last_time = time.monotonic()

        self._serial_drop = False

    @property
    def world(self) -> object | None:
        return self._world

    @world.setter
    def world(self, w: object) -> None:
        self._world = w

    def receive_setpoint_frame(self, frame: bytes) -> None:
        """Processa um quadro de setpoint (contrato 3) com CRC.

        Espelha o SetpointFrameDecoder do firmware.
        """
        if self._serial_drop:
            return

        text = frame.decode("utf-8", errors="replace").strip()
        if "*" not in text:
            return

        payload_str, checksum = text.rsplit("*", 1)
        if len(checksum) != 2:
            return

        expected = crc8_hex(payload_str.encode("utf-8"))
        if checksum != expected:
            return

        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError:
            return

        if "w_esq" not in data or "w_dir" not in data:
            return

        self.setpoint_w_esq = float(data["w_esq"])
        self.setpoint_w_dir = float(data["w_dir"])

        garfo_str = data.get("garfo", "parar")
        try:
            self.setpoint_garfo = ForkCommand(garfo_str)
        except ValueError:
            self.setpoint_garfo = ForkCommand.PARAR

        self.setpoint_valid = True
        self.last_setpoint_time = time.monotonic()

    def step(self, dt: float) -> None:
        """Avança a simulação por dt segundos.

        Roda internamente o PID a ~100 Hz acumulando sub-passos.
        """
        now = time.monotonic()

        if self.setpoint_valid and config.EMU_SETPOINT_TIMEOUT_MS > 0:
            elapsed_ms = (now - self.last_setpoint_time) * 1000
            if elapsed_ms > config.EMU_SETPOINT_TIMEOUT_MS:
                self._motors_stop()
                self.setpoint_valid = False

        pid_dt = 1.0 / config.EMU_PID_HZ
        self._pid_accumulator += dt
        while self._pid_accumulator >= pid_dt:
            self._pid_accumulator -= pid_dt
            self._pid_step(pid_dt)

        self._apply_fork(dt)

        if self._world is not None:
            from app.sim.world import SimWorld

            if isinstance(self._world, SimWorld):
                self._world.step(self.measured_esq, self.measured_dir, dt)

    def _pid_step(self, dt: float) -> None:
        """Um passo de PID + motor."""
        if self.setpoint_valid:
            self.pid_esq.setpoint = self.setpoint_w_esq
            self.pid_dir.setpoint = self.setpoint_w_dir

            u_esq = self.pid_esq.update(self.measured_esq, dt)
            u_dir = self.pid_dir.update(self.measured_dir, dt)

            self.measured_esq = self.motor_esq.step(u_esq, dt)
            self.measured_dir = self.motor_dir.step(u_dir, dt)
        else:
            self.measured_esq = self.motor_esq.step(0.0, dt)
            self.measured_dir = self.motor_dir.step(0.0, dt)

    def _apply_fork(self, dt: float) -> None:
        """Aplica comando do garfo com fim-de-curso."""
        if not self.setpoint_valid:
            return

        cmd = self.setpoint_garfo

        if cmd == ForkCommand.SUBIR:
            if self.fork_height >= config.EMU_FORK_MAX_HEIGHT:
                return
            self.fork_height += config.EMU_FORK_SPEED * dt
            self.fork_height = min(self.fork_height, config.EMU_FORK_MAX_HEIGHT)

        elif cmd == ForkCommand.DESCER:
            if self.fork_height <= config.EMU_FORK_MIN_HEIGHT:
                return
            self.fork_height -= config.EMU_FORK_SPEED * dt
            self.fork_height = max(self.fork_height, config.EMU_FORK_MIN_HEIGHT)

    def _motors_stop(self) -> None:
        """Estado seguro: zera motores e PID."""
        self.pid_esq.reset()
        self.pid_dir.reset()
        self.motor_esq.omega = 0.0
        self.motor_dir.omega = 0.0
        self.measured_esq = 0.0
        self.measured_dir = 0.0

    def generate_sensors_frame(self) -> bytes:
        """Gera quadro de sensores (contrato 4) com CRC.

        Returns:
            Quadro ``<json>*<crc8hex>\\n`` pronto para o serial_loop.
        """
        mpu = self._generate_mpu()

        data = {
            "enc": {"esq": round(self.measured_esq, 4), "dir": round(self.measured_dir, 4)},
            "mpu": {
                "ax": round(mpu["ax"], 4),
                "ay": round(mpu["ay"], 4),
                "az": round(mpu["az"], 4),
                "gx": round(mpu["gx"], 4),
                "gy": round(mpu["gy"], 4),
                "gz": round(mpu["gz"], 4),
                "temp_c": round(mpu["temp_c"], 2),
            },
            "bms": None,
        }

        payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        checksum = crc8_hex(payload.encode("utf-8"))
        return f"{payload}*{checksum}\n".encode()

    def _generate_mpu(self) -> dict:
        """Gera dados crus do MPU-6050 a partir da pose do robô."""
        noise_scale = 0.05

        ax = self._rng.gauss(0, noise_scale)
        ay = self._rng.gauss(0, noise_scale)
        az = 9.81 + self._rng.gauss(0, noise_scale)

        gx = self._rng.gauss(0, 0.1)
        gy = self._rng.gauss(0, 0.1)
        gz = self._rng.gauss(0, 0.1)

        if self._world is not None:
            from app.sim.world import SimWorld

            if isinstance(self._world, SimWorld):
                r = config.WHEEL_RADIUS_R_CM
                omega_z = (self.measured_dir - self.measured_esq) * r / config.WHEEL_BASE_L_CM
                gz = math.degrees(omega_z) + self._rng.gauss(0, 0.1)

        temp_c = 25.0 + self._rng.gauss(0, 0.5)

        return {"ax": ax, "ay": ay, "az": az, "gx": gx, "gy": gy, "gz": gz, "temp_c": temp_c}

    def fork_at_top(self) -> bool:
        return self.fork_height >= config.EMU_FORK_MAX_HEIGHT

    def fork_at_bottom(self) -> bool:
        return self.fork_height <= config.EMU_FORK_MIN_HEIGHT

    def set_serial_drop(self, drop: bool) -> None:
        """Injeta/remove queda de serial."""
        self._serial_drop = drop
        if drop:
            self._motors_stop()
            self.setpoint_valid = False
