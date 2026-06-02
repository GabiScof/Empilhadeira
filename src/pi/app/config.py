"""Constantes e parâmetros de configuração do app do Raspberry Pi.

Centraliza **todos** os números do alto nível. Nenhum número mágico deve aparecer
fora deste módulo (convenção da Seção 10).

Os parâmetros marcados com ``TODO(equipe): confirmar`` são **placeholders** — a
equipe ainda não fechou o valor real (Seção 3 da AGENTS.md). NÃO trate placeholder
como verdade nem otimize em cima dele.

[ref: Seção 3 da AGENTS.md]
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Rede / WebSocket (Frontend ↔ Pi)
# ---------------------------------------------------------------------------
# Host/porta do servidor FastAPI/WebSocket. Lidos de .env quando presente.
WS_HOST: str = os.getenv("PI_HOST", "0.0.0.0")
WS_PORT: int = int(os.getenv("PI_PORT", "8000"))

# Taxa de telemetria Pi → Frontend.
TELEMETRY_HZ: float = 20.0

# Watchdog do canal de comando: se nenhum comando chegar nesse intervalo durante o
# modo MANUAL com o robô andando, o Pi força PARADO. [ref: Seção 4 e 7]
COMMAND_WATCHDOG_MS: int = 500  # TODO(equipe): confirmar (depende do RTT alvo < 170 ms).

# ---------------------------------------------------------------------------
# Serial (Pi ↔ ESP32)
# ---------------------------------------------------------------------------
SERIAL_PORT: str = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUDRATE: int = int(os.getenv("SERIAL_BAUDRATE", "115200"))  # decisão fechada (Seção 2)
SERIAL_HZ: float = 20.0  # taxa de troca Pi↔ESP32 (decisão fechada)

# ---------------------------------------------------------------------------
# Cinemática diferencial — [ref: Seção 3 e 7]
# ---------------------------------------------------------------------------
WHEEL_BASE_L_CM: float | None = None  # TODO(equipe): confirmar — distância entre rodas (cm).
WHEEL_RADIUS_R_CM: float | None = None  # TODO(equipe): confirmar — raio da roda (cm).

# Saturação do joystick → (v, ω) no modo manual.
MAX_LINEAR_SPEED: float | None = None  # TODO(equipe): confirmar — v máx (cm/s).
MAX_ANGULAR_SPEED: float | None = None  # TODO(equipe): confirmar — ω máx (rad/s).

# ---------------------------------------------------------------------------
# Navegação automática — [ref: Seção 3 e 7]
# Objetivo: X≈0, Pitch≈0, Z≈Zref.  v = Kz·(Z−Zref); ω = Kx·X + Kp_pitch·Pitch
# ---------------------------------------------------------------------------
NAV_KZ: float | None = None  # TODO(equipe): confirmar — ganho de aproximação (eixo Z).
NAV_KX: float | None = None  # TODO(equipe): confirmar — ganho de alinhamento lateral (X).
NAV_KP_PITCH: float | None = None  # TODO(equipe): confirmar — ganho de orientação (Pitch).
ZREF_CM: float | None = (
    None  # TODO(equipe): confirmar — distância de parada (~5 cm? depende do garfo).
)

# Perda de tag: nº de frames sem detecção que leva a PARADO (>5 frames ~250 ms @20 Hz).
TAG_LOST_FRAMES: int = 5  # [ref: Seção 7]

# ---------------------------------------------------------------------------
# Visão / AprilTag — [ref: Seção 3 e 8]
# ---------------------------------------------------------------------------
APRILTAG_FAMILY: str = "tag25h9"  # decisão fechada (Seção 8)
APRILTAG_SIZE_CM: float | None = None  # TODO(equipe): confirmar — tamanho físico da tag (cm).

# Intrínsecos da câmera usados na estimativa de pose.
# Enquanto a calibração real não entrar, estes valores vêm do protótipo.
CAMERA_FX: float = 799.3907361857031
CAMERA_FY: float = 794.2843064465196
CAMERA_CX: float = 399.03967921864864
CAMERA_CY: float = 273.1926221127301

CAMERA_PARAMS: tuple[float, float, float, float] = (
    CAMERA_FX,
    CAMERA_FY,
    CAMERA_CX,
    CAMERA_CY,
)

# Offset extrínseco câmera → garfo (alinhar câmera ≠ alinhar garfo). [ref: Seção 4]
CAMERA_TO_FORK_OFFSET_CM: tuple[float, float, float] | None = (
    None  # TODO(equipe): confirmar (x, y, z).
)

# Arquivo de intrínsecos da câmera (saída da calibração).
CAMERA_INTRINSICS_PATH: Path = (
    Path(__file__).resolve().parent.parent / "calibracao" / "camera_intrinsics.json"
)

# ---------------------------------------------------------------------------
# Plataforma / mecânica — parâmetros em aberto — [ref: Seção 3]
# ---------------------------------------------------------------------------
# INCONSISTÊNCIA ABERTA: a intro do relatório diz ~1 kg, mas o cálculo do garfo
# usou 0,1 kg. A equipe precisa fechar o valor real antes de dimensionar o motor.
PALLET_MASS_KG: float | None = None  # TODO(equipe): confirmar — massa real do pallet (kg).

# Versão/torque do motor do garfo depende da massa real (a versão 40 rpm pode estar
# subdimensionada).
FORK_MOTOR_VERSION: str | None = None  # TODO(equipe): confirmar — versão/torque do motor do garfo.
