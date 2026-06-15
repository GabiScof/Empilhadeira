"""Constantes e parâmetros de configuração do app do Raspberry Pi.

Centraliza **todos** os números do alto nível. Nenhum número mágico deve aparecer
fora deste módulo (convenção da Seção 10).

Os parâmetros marcados com ``PROVISÓRIO — TODO(equipe): confirmar`` são **placeholders**
com valores provisórios razoáveis para simulação. A equipe deve medir e confirmar
cada um no hardware real antes de usar em produção.

[ref: Seção 3 da AGENTS.md]
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Modo de simulação
# ---------------------------------------------------------------------------
SIM: bool = os.getenv("SIM", "0") == "1"

# ---------------------------------------------------------------------------
# Rede / WebSocket (Frontend ↔ Pi)
# ---------------------------------------------------------------------------
WS_HOST: str = os.getenv("PI_HOST", "0.0.0.0")
WS_PORT: int = int(os.getenv("PI_PORT", "8000"))

TELEMETRY_HZ: float = 20.0

# Frequência do loop de controle (navegação + máquina de estados → setpoint).
# Roda independente da cadência de comando do operador (o frontend é orientado a
# evento, não envia stream contínuo).
CONTROL_HZ: float = 20.0

# PROVISÓRIO — TODO(equipe): confirmar (depende do RTT alvo < 170 ms)
COMMAND_WATCHDOG_MS: int = 500

# ---------------------------------------------------------------------------
# Serial (Pi ↔ ESP32)
# ---------------------------------------------------------------------------
SERIAL_PORT: str = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUDRATE: int = int(os.getenv("SERIAL_BAUDRATE", "115200"))
SERIAL_HZ: float = 20.0

# ---------------------------------------------------------------------------
# Cinemática diferencial — [ref: Seção 3 e 7]
# ---------------------------------------------------------------------------
# PROVISÓRIO — TODO(equipe): confirmar — distância entre rodas (cm).
# Estimado para chassi Lego em escala; medir no robô montado.
WHEEL_BASE_L_CM: float = 15.0

# PROVISÓRIO — TODO(equipe): confirmar — raio da roda (cm).
# Roda Lego NXT ~56 mm de diâmetro → r ≈ 2.8 cm.
WHEEL_RADIUS_R_CM: float = 2.8

# PROVISÓRIO — TODO(equipe): confirmar — v máx (cm/s).
# Conservador para ambiente interno controlado.
MAX_LINEAR_SPEED: float = 30.0

# PROVISÓRIO — TODO(equipe): confirmar — ω máx (rad/s).
MAX_ANGULAR_SPEED: float = 3.0

# ---------------------------------------------------------------------------
# Navegação automática — [ref: Seção 3 e 7]
# ---------------------------------------------------------------------------
# PROVISÓRIO — TODO(equipe): confirmar — ganho de aproximação (eixo Z).
NAV_KZ: float = 0.5

# PROVISÓRIO — TODO(equipe): confirmar — ganho de alinhamento lateral (X).
NAV_KX: float = 2.0

# PROVISÓRIO — TODO(equipe): confirmar — ganho de orientação (Pitch).
NAV_KP_PITCH: float = 0.5

# PROVISÓRIO — TODO(equipe): confirmar — distância de parada (~5 cm? depende do garfo).
ZREF_CM: float = 5.0

TAG_LOST_FRAMES: int = 5

# Limiar de oscilação para trocar de estratégia A para B na navegação.
NAV_OSCILLATION_THRESHOLD: float = 3.0  # PROVISÓRIO — TODO(equipe): confirmar
NAV_OSCILLATION_WINDOW: int = 10  # nº de amostras para detectar oscilação

# FOV/foco: distância mínima abaixo da qual a tag pode sair do FOV.
NAV_MIN_Z_FOR_PRIMARY: float = 8.0  # PROVISÓRIO — TODO(equipe): confirmar (cm)

# Tolerâncias para fallback sequencial
NAV_ALIGN_X_TOL: float = 0.5  # cm — tolerância lateral para considerar alinhado
NAV_ALIGN_PITCH_TOL: float = 2.0  # graus — tolerância angular

# ---------------------------------------------------------------------------
# Visão / AprilTag — [ref: Seção 3 e 8]
# ---------------------------------------------------------------------------
APRILTAG_FAMILY: str = "tag25h9"

# PROVISÓRIO — TODO(equipe): confirmar — tamanho físico da tag (cm).
APRILTAG_SIZE_CM: float = 5.0

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

# PROVISÓRIO — TODO(equipe): confirmar (x, y, z) em cm.
# Sem offset até a equipe medir a posição relativa câmera-garfo.
CAMERA_TO_FORK_OFFSET_CM: tuple[float, float, float] = (0.0, 0.0, 0.0)

CAMERA_INTRINSICS_PATH: Path = (
    Path(__file__).resolve().parent.parent / "calibracao" / "camera_intrinsics.json"
)

# ---------------------------------------------------------------------------
# Plataforma / mecânica — [ref: Seção 3]
# ---------------------------------------------------------------------------
# PROVISÓRIO — TODO(equipe): confirmar — massa real do pallet (kg).
# INCONSISTÊNCIA ABERTA: a intro do relatório diz ~1 kg, mas o cálculo do garfo
# usou 0,1 kg. Usando 0,1 kg como padrão conservador para o garfo.
PALLET_MASS_KG: float = 0.1

# PROVISÓRIO — TODO(equipe): confirmar — versão/torque do motor do garfo.
FORK_MOTOR_VERSION: str = "JGY-370-12V-40rpm"

# ---------------------------------------------------------------------------
# Constantes do emulador / simulação (espelho do firmware)
# ---------------------------------------------------------------------------
# PID (espelha config.h do firmware)
EMU_PID_KP: float = 20.0
EMU_PID_KI: float = 5.0
EMU_PID_KD: float = 1.0
EMU_PID_INTEGRAL_LIMIT: float = 500.0
EMU_PID_HZ: float = 100.0

# Motor Lego NXT 53787: ~117 rpm ≈ 12.25 rad/s no eixo de saída
EMU_MAX_OMEGA: float = 12.25
EMU_MOTOR_TAU: float = 0.05  # constante de tempo 1ª ordem (s)
EMU_MAX_DUTY: int = 255
EMU_LEDC_RESOLUTION_BITS: int = 8

# Garfo JGY-370-12V worm gear
EMU_FORK_DUTY: int = 180
EMU_FORK_SPEED: float = 2.0  # cm/s de deslocamento vertical — PROVISÓRIO — TODO(equipe): confirmar
EMU_FORK_MIN_HEIGHT: float = 0.0  # cm
EMU_FORK_MAX_HEIGHT: float = 10.0  # cm — PROVISÓRIO — TODO(equipe): confirmar

# Encoder Lego NXT 53787
EMU_ENCODER_PPR: int = 360

# Watchdog de setpoint (espelha SETPOINT_TIMEOUT_MS do firmware)
EMU_SETPOINT_TIMEOUT_MS: int = 200

# Mundo de simulação
SIM_ARENA_WIDTH: float = 200.0  # cm
SIM_ARENA_HEIGHT: float = 200.0  # cm
SIM_DEFAULT_SEED: int = 42

# Visão sintética
SIM_VISION_FOV_H_DEG: float = 60.0  # campo de visão horizontal (graus)
SIM_VISION_MIN_RANGE: float = 3.0  # cm — distância mínima de detecção
SIM_VISION_MAX_RANGE: float = 150.0  # cm — distância máxima de detecção
SIM_VISION_NOISE_STD_CM: float = 0.2  # desvio-padrão do ruído de posição (cm)
SIM_VISION_NOISE_STD_DEG: float = 0.5  # desvio-padrão do ruído de ângulo (graus)
