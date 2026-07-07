"""Constantes e parâmetros de configuração do app do Raspberry Pi.

Centraliza **todos** os números do alto nível. Nenhum número mágico deve aparecer
fora deste módulo (convenção da Seção 10).

Os parâmetros marcados com ``PROVISÓRIO — TODO(equipe): confirmar`` são **placeholders**
com valores provisórios razoáveis para simulação. A equipe deve medir e confirmar
cada um no hardware real antes de usar em produção.

[ref: Seção 3 da AGENTS.md]
"""

from __future__ import annotations

import math
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

# Timeout do canal de comando: se nenhum comando chegar neste intervalo, o Pi força
# PARADO independentemente do modo. [ref: Seção 4 e 7]
# RTT alvo < 170 ms; o frontend envia heartbeat a ~100 ms, então 400 ms é conservador
# e seguro — ajustar empiricamente conforme a rede da PUC.
# Valor de contrato vindo de main (real); nome usado pelo state_machine.
COMMAND_WATCHDOG_MS: int = 400  # ajustável; deve ser >> RTT + jitter

# ---------------------------------------------------------------------------
# Serial (Pi ↔ ESP32)
# ---------------------------------------------------------------------------
SERIAL_PORT: str = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUDRATE: int = int(os.getenv("SERIAL_BAUDRATE", "115200"))
SERIAL_HZ: float = 20.0

# Ciclos consecutivos sem sensor que ativam o watchdog serial → PARADO (~250 ms @20 Hz).
SERIAL_LOST_FRAMES: int = 5  # [ref: Seção 7]

# ---------------------------------------------------------------------------
# Cinemática diferencial — [ref: Seção 3 e 7]
# ---------------------------------------------------------------------------
# PROVISÓRIO — TODO(equipe): confirmar — distância entre rodas (cm).
# Estimado para chassi Lego em escala; medir no robô montado.
WHEEL_BASE_L_CM: float = 15.0

# PROVISÓRIO — TODO(equipe): confirmar — raio da roda (cm).
# Roda Lego NXT ~56 mm de diâmetro → r ≈ 2.8 cm.
WHEEL_RADIUS_R_CM: float = 2.7

# MEDIDO NA BANCADA (2026-07-06): 100 cm em 4,16 s a talo cheio no chão
# → v_máx real = 24,0 cm/s. Gravado a ~80% (folga p/ o PID corrigir e p/ a
# bateria cair sem saturar). Remedir se trocar bateria/pneus/carga.
MAX_LINEAR_SPEED: float = 19.0

# DERIVADO do v medido — PROVISÓRIO até cronometrar o giro (3.1 do test plan):
# teto físico ω = 2·v_máx/L = 2·24/15 ≈ 3,2 rad/s → 80% ≈ 2,5.
# Confirmar com 1 volta no lugar cronometrada (ω = 2π/t) e ajustar.
MAX_ANGULAR_SPEED: float = 2.5

# ---------------------------------------------------------------------------
# Navegação automática — [ref: Seção 3 e 7]
# ---------------------------------------------------------------------------
# PROVISÓRIO — TODO(equipe): confirmar — ganho de aproximação (eixo Z).
NAV_KZ: float = 0.5

# PROVISÓRIO — TODO(equipe): confirmar — ganho de alinhamento lateral (X).
# Valor baixo para que ruído de visão (±0.5 cm) não gere omega que cancele v.
NAV_KX: float = 0.80

# PROVISÓRIO — TODO(equipe): confirmar — ganho de orientação (Pitch).
# Suave: com a fórmula de pitch corrigida, o valor nominal é ~0° e correções
# grandes não são necessárias.
NAV_KP_PITCH: float = 0.1

# PROVISÓRIO — TODO(equipe): confirmar — distância de parada.
# 15 cm dá margem para frenagem e mantém a tag confortavelmente no FOV/foco.
# Com 5 cm o PID não freia a tempo e o robô ultrapassa a tag.
ZREF_CM: float = 15.0

TAG_LOST_FRAMES: int = 5

# Limiar de oscilação para trocar de estratégia A para B na navegação.
NAV_OSCILLATION_THRESHOLD: float = 3.0  # PROVISÓRIO — TODO(equipe): confirmar
NAV_OSCILLATION_WINDOW: int = 10  # nº de amostras para detectar oscilação

# FOV/foco: distância mínima abaixo da qual a tag pode sair do FOV.
NAV_MIN_Z_FOR_PRIMARY: float = 8.0  # PROVISÓRIO — TODO(equipe): confirmar (cm)

# Perfil de desaceleração — evita overshoot do ZREF
# v_max = sqrt(2 · a_decel · d).  O PID do emulador (Kd=1 a 100 Hz) causa
# windup de integral que atrasa a frenagem; sem este limite o robô ultrapassa a tag.
NAV_DECEL_CMS2: float = 5.0  # PROVISÓRIO — TODO(equipe): confirmar (cm/s²)
NAV_MAX_APPROACH_SPEED: float = 15.0  # PROVISÓRIO — TODO(equipe): confirmar (cm/s)

# Tolerâncias para fallback sequencial
NAV_ALIGN_X_TOL: float = 0.5  # cm — tolerância lateral para considerar alinhado
NAV_ALIGN_PITCH_TOL: float = 2.0  # graus — tolerância angular

# ---------------------------------------------------------------------------
# Visão / AprilTag — [ref: Seção 3 e 8]
# ---------------------------------------------------------------------------
APRILTAG_FAMILY: str = "tag25h9"

# PROVISÓRIO — TODO(equipe): confirmar — tamanho físico da tag (cm).
APRILTAG_SIZE_CM: float = 4.0

# Fallbacks = câmera nova calibrada em 2026-07-07 a 1280x720 (a fonte da
# verdade é calibracao/camera_intrinsics.json — estes valores só valem se o
# JSON sumir E REQUIRE_CAMERA_CALIBRATION=0).
CAMERA_FX: float = 998.168
CAMERA_FY: float = 998.168
CAMERA_CX: float = 643.338
CAMERA_CY: float = 372.688

CAMERA_PARAMS: tuple[float, float, float, float] = (
    CAMERA_FX,
    CAMERA_FY,
    CAMERA_CX,
    CAMERA_CY,
)

# Offset câmera→garfo em cm, SOMADO à leitura (pose.py: z_cm += offset_z).
# A lente fica ATRÁS da ponta do garfo → a distância garfo→tag é MENOR que a
# lente→tag → offset_z NEGATIVO. (Sinal validado na bancada 2026-07-07: com
# +25.5 o z saía ~2x a distância real.) Após o offset, z_cm = distância da
# PONTA DO GARFO até a tag; ZREF_CM/standoff referem-se a ela. y (desnível
# vertical) é ignorado pelo contrato.
# AJUSTE EMPÍRICO NA BANCADA (2026-07-07): com -21,3 o z zerava com a tag a
# 8 cm da ponta do garfo (medida geométrica ≠ referência real da lente) →
# -21,3 + 8 = -13,3. Validar: tag a 30 cm da ponta do garfo → z_cm ≈ 30;
# encostada na ponta → z_cm ≈ 0.
CAMERA_TO_FORK_OFFSET_CM: tuple[float, float, float] = (0.0, -14.2, -13.3)

# Inclinação da câmera para BAIXO, em graus (0 = nivelada). A câmera fica no
# topo do trilho do garfo, acima das tags, e precisa olhar para baixo para
# vê-las de perto — mas o z do AprilTag é medido ao longo do EIXO ÓPTICO
# (hipotenusa), não na horizontal: sem compensação o erro cresce ao aproximar
# (a 15 cm horizontais com 20 cm de desnível, +66%). pose.py rotaciona a pose
# por este ângulo antes de extrair z/x/pitch → distâncias HORIZONTAIS reais.
# COMO MEDIR: tag centralizada NA IMAGEM; medir a distância horizontal d e o
# desnível Δh entre o centro da lente e o centro da tag → tilt = atan(Δh/d),
# em graus. (Ou inclinômetro do celular apoiado no corpo da câmera.)
# Depois de definir o tilt, RECALIBRAR o CAMERA_TO_FORK_OFFSET_CM (offset
# medido sem compensação absorve o erro da hipotenusa e só vale numa distância).
# MEDIDO NA BANCADA (2026-07-07) para a CÂMERA NOVA, tag centralizada na
# imagem: lente a 27,0 cm do chão · centro da tag a 15,3 cm · d = 27,9 cm
#   → Δh = 11,7 cm → tilt = atan(11,7/27,9) = 22,7°.
# (Montagem anterior/câmera antiga: 28,4° — lente estava a 29,5 cm.)
# Incidência no standoff de 15 cm: atan(11,7/15) ≈ 38° — confortável (< 45°).
# Validar: tag a 30 cm horizontais da ponta do garfo → z≈30; a 15 → z≈15.
CAMERA_TILT_DEG: float = 22.7

CAMERA_INTRINSICS_PATH: Path = (
    Path(__file__).resolve().parent.parent / "calibracao" / "camera_intrinsics.json"
)

# Índice do dispositivo de câmera para cv2.VideoCapture.
# FIXADO em 1 (câmera nova enumera como /dev/video1; ajustado na bancada 2026-07-07).
# Propositalmente SEM env override — o valor certo mora aqui; se a enumeração
# de dispositivos mudar (trocar porta USB/câmera), editar esta linha.
CAMERA_INDEX: int = 1
# Defaults = resolução da CALIBRAÇÃO (câmera nova: 1280×720). São só fallback:
# quem abre a câmera (vision_loop/teste_cam) força a resolução anotada no JSON
# de calibração — capturar em outra invalida fx/fy/cx/cy silenciosamente.
CAMERA_FRAME_WIDTH: int = 1280
CAMERA_FRAME_HEIGHT: int = 720

# Decimação do detector AprilTag (1.0 = desligada). A detecção escala com o
# nº de pixels: a 1280×720 no Pi, 2.0 corta ~4x o custo detectando nos quads
# em meia-resolução (os cantos ainda são refinados em resolução cheia — a
# precisão da pose quase não muda). Subir para 2.0 se o loop de visão ficar
# lento (< ~15 fps) com a câmera 720p.
APRILTAG_QUAD_DECIMATE: float = 2.0

# Se True, o modo real exige calibração válida da câmera no boot (recomendado:
# os intrínsecos placeholder de config NÃO servem para o hardware real).
REQUIRE_CAMERA_CALIBRATION: bool = os.getenv("REQUIRE_CAMERA_CALIBRATION", "1") == "1"

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

# Garfo JGY-370-12V worm gear (espelha FORK_DUTY do firmware/config.h —
# subiu 180→220 na bancada para levantar com carga)
EMU_FORK_DUTY: int = 220
EMU_FORK_SPEED: float = 2.0  # cm/s de deslocamento vertical — PROVISÓRIO — TODO(equipe): confirmar
EMU_FORK_MIN_HEIGHT: float = 0.0  # cm
EMU_FORK_MAX_HEIGHT: float = 10.0  # cm — PROVISÓRIO — TODO(equipe): confirmar

# Encoder Lego NXT 53787 — 360 ciclos de quadratura/rev x4 (decodificação
# completa nas fases A e B; espelha ENCODER_PPR do firmware/config.h)
EMU_ENCODER_PPR: int = 1440

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

# ---------------------------------------------------------------------------
# Modelo de mundo — [ref: Seção 2 do mega-prompt]
# ---------------------------------------------------------------------------
# Mapa padrão — selecionável por .env/CLI/UI.
# HARDCODED (2026-07-07): mapa REAL medido da arena (80x160, april_tag_id
# preenchidos). Sem env — o MAP= do .env apontava para o mapa antigo sem
# april_tag_id e o robô real não resolvia nenhuma tag contra o mapa.
# Troca em runtime continua possível: POST /maps/load/<nome>.
DEFAULT_MAP: str = "corredor_6tags_80x160"

# Diretório dos mapas
MAPS_DIR: Path = Path(__file__).resolve().parent.parent / "maps"

# ---------------------------------------------------------------------------
# Parâmetros SI — usados internamente pela navegação/EKF/mundo
# ---------------------------------------------------------------------------
# Os valores abaixo derivam dos parâmetros em cm já existentes.
# O Pi usa SI internamente; converte só na fronteira do protocolo.
WHEELBASE_M: float = WHEEL_BASE_L_CM / 100.0    # PROVISÓRIO — TODO(equipe): confirmar
WHEEL_RADIUS_M: float = WHEEL_RADIUS_R_CM / 100.0  # PROVISÓRIO — TODO(equipe): confirmar
ENCODER_PPR: int = EMU_ENCODER_PPR  # TODO(equipe): confirmar

MAX_LINEAR_SPEED_MS: float = MAX_LINEAR_SPEED / 100.0  # m/s
MAX_ANGULAR_SPEED_RADS: float = MAX_ANGULAR_SPEED  # já em rad/s

# ---------------------------------------------------------------------------
# EKF 2D — [ref: Seção 3 do mega-prompt]
# ---------------------------------------------------------------------------
EKF_Q_XY: float = 0.001   # TODO(equipe): ruído de processo posição (m²)
EKF_Q_THETA: float = 0.002  # TODO(equipe): ruído de processo heading (rad²)
EKF_R_XY: float = 0.01    # TODO(equipe): ruído de observação tag posição (m²)
EKF_R_THETA: float = 0.05  # TODO(equipe): ruído de observação tag heading (rad²)
EKF_MAHALANOBIS_GATE: float = 3.0  # TODO(equipe): limiar de Mahalanobis

# ---------------------------------------------------------------------------
# IMU / Giroscópio — calibração de bias (zero-rate) e convenção de eixo
# ---------------------------------------------------------------------------
# Na PARTIDA (robô parado) o GyroCalibrator mede a gravidade p/ descobrir o
# eixo vertical (yaw) e seu sinal, e estima o bias de taxa-zero. Como o
# MPU-6050 é destro, gravidade + sensor bastam p/ fixar o sinal do yaw — sem
# teste de giro manual. Logo a POSIÇÃO/ORIENTAÇÃO do IMU no chassi é
# irrelevante, desde que o eixo vertical não fique deitado.
IMU_AUTO_ORIENT: bool = os.getenv("IMU_AUTO_ORIENT", "1") not in ("0", "false", "False")
# Usado só quando IMU_AUTO_ORIENT=0 (modo manual): assume Z vertical c/ este sinal.
IMU_GYRO_Z_SIGN: float = float(os.getenv("IMU_GYRO_Z_SIGN", "1.0"))
IMU_TILT_WARN_DEG: float = 10.0  # avisa se a placa estiver inclinada acima disto
GYRO_CAL_MIN_SAMPLES: int = 40  # amostras paradas p/ travar a calibração (~2s @ 20Hz)
GYRO_CAL_STATIONARY_EPS_RADS: float = 0.05  # |ω| roda (cmd e medido) < isto = parado
GYRO_CAL_TRACK_ALPHA: float = 0.01  # EMA p/ rastrear drift térmico após calibrado

# ---------------------------------------------------------------------------
# Navegação genérica — [ref: Seção 4 do mega-prompt]
# ---------------------------------------------------------------------------
NAV_K_DIST: float = 1.5     # ganho proporcional distância → v (1/s); cap em MAX_LINEAR_SPEED_MS
NAV_K_HEADING: float = 2.5  # ganho proporcional heading → ω (1/s); cap em MAX_ANGULAR_SPEED_RADS
NAV_POS_TOL_M: float = 0.02  # tolerância de posição (m)
NAV_HEADING_TOL_RAD: float = 0.07  # ~4° — folga p/ o piso de ω não oscilar (era 2°)

# Pisos de velocidade (anti atrito estático) — bancada 2026-07-07: a malha
# proporcional comanda velocidades minúsculas perto do alvo e o chão engole
# (roda zumbe, robô parado, dock "lento/fraco" até estourar timeout). Fora da
# tolerância, nunca comandar abaixo disto:
NAV_MIN_V_MS: float = 0.09        # ~3.3 rad/s de roda — acima da zona stick-slip
NAV_MIN_OMEGA_RADS: float = 1.0   # giro no lugar (skid) exige mais torque

# TETO do giro no lugar (só segmentos TURN) — bancada 2026-07-07: girar a
# 2,5 rad/s derrapa as rodas (skid), a odometria conta rotação que não houve
# e o θ do EKF sai errado → o AVANÇO seguinte nasce torto e corrige em arco
# ("não parece curva discreta"). Janela estreita 1,0–1,6 rad/s = giro
# consistente: nem trava (piso) nem derrapa (teto).
NAV_TURN_MAX_OMEGA_RADS: float = 1.6

NAV_FALLBACK_V_MS: float = 0.08  # velocidade fixa quando K_DIST=0 (fallback de segurança)
NAV_FALLBACK_OMEGA_RADS: float = 1.0  # vel. angular fixa quando K_HEADING=0 (fallback)
NAV_MAX_SEGMENT_TIME_S: float = 45.0  # timeout por segmento (margem p/ corredores longos)

# ---------------------------------------------------------------------------
# Simulação — injeção de falhas de visão
# ---------------------------------------------------------------------------
SIM_VISION_BLUR_PROB: float = 0.0   # probabilidade de blur por frame
SIM_VISION_DROP_PROB: float = 0.0   # probabilidade de drop (sem detecção)
SIM_ENCODER_NOISE_STD: float = 0.05  # desvio-padrão do ruído de encoder (rad/s)
SIM_GYRO_DRIFT_RADS: float = 0.001  # drift do giroscópio (rad/s)
SIM_SLIP_FRICTION: float = 1.0  # multiplicador de atrito desigual

# Standoff de aproximação: distância em frente ao tag onde o robô para.
# Garante que o robô chega PELA FRENTE da tag (face visível).
TAG_APPROACH_STANDOFF_M: float = float(os.getenv("TAG_STANDOFF_M", "0.15"))

# ---------------------------------------------------------------------------
# Dock-to-tag — aproximação por segmentos (FORWARD/TURN) a UMA tag avulsa.
#
# Modo de teste independente da missão: o robô vê uma tag, planeja uma rota
# de segmentos discretos (avança / gira 90°) até parar PELA FRENTE dela e
# executa via SegmentExecutor (mesma malha externa da missão). Diferente do
# navegador legado (`NavigationController`), que servo-controla continuamente
# sobre a leitura da tag.
#
# ALVO: ROBÔ REAL. Consome as mesmas leituras (z_cm/x_cm/pitch_deg) que o
# navegador legado já usa no hardware.
#
# OPT-IN: desligado por padrão. Ligado, substitui o navegador legado no ramo
# AUTOMATICO-sem-missão. Com DOCK_TO_TAG=0 o comportamento é idêntico ao atual.
# [ref: docs/dock-to-tag.md]
# ---------------------------------------------------------------------------
# HARDCODED True (2026-07-07): o env desligado a cada restart derrubava o
# AUTOMATICO no caminho legado ("tag perdida" imediato). Dock e o modo padrao
# do AUTOMATICO-sem-missao; desligavel em runtime via POST /dock/disable.
DOCK_TO_TAG_ENABLED: bool = True

# Estratégia de alvo:
#   "line_of_sight" (DEFAULT, real) — para no standoff em cima da linha de visão
#       até a tag, de frente para ela. Usa SÓ z_cm/x_cm (bem definidos, iguais
#       ao navegador legado). NÃO depende de convenção de yaw → seguro no real.
#   "tag_normal" — quadra com a FACE da tag (aproxima pela normal). Mais preciso
#       para pallet/garfo, mas depende do yaw da tag (ver offset abaixo). Use só
#       depois de validar a convenção com uma tag física.
DOCK_MODE: str = os.getenv("DOCK_MODE", "line_of_sight")

# Distância em frente à tag onde o robô estaciona (m). Reusa o standoff da missão.
DOCK_STANDOFF_M: float = float(os.getenv("DOCK_STANDOFF_M", str(TAG_APPROACH_STANDOFF_M)))

# Detecções consecutivas exigidas antes de planejar (debounce anti-ruído).
DOCK_MIN_DETECTIONS: int = int(os.getenv("DOCK_MIN_DETECTIONS", "3"))

# Offset da convenção de yaw (SÓ usado por DOCK_MODE="tag_normal"):
#   tag_yaw_mundo = theta_robô + radianos(pitch_deg) + DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD
#
# HARDCODED π — CONVENÇÃO UNIFICADA (validada na bancada 2026-07-07): o
# pitch da câmera real é NEGADO na fronteira (pose.py; medição: borda
# esquerda da tag perto → câmera dava −38°, projeto exige +), o que o deixa
# na MESMA convenção da visão sintética. Com isso o offset é π nos dois
# mundos (tag de frente: pitch=0 → yaw da tag = θ_robô + π, apontando de
# volta para o robô). O modo "line_of_sight" IGNORA este valor.
DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD: float = math.pi

# ---------------------------------------------------------------------------
# Missão — [ref: Seção 5 do mega-prompt]
# ---------------------------------------------------------------------------
MISSION_SEED: int = int(os.getenv("MISSION_SEED", "42"))
# TODO(equipe): confirmar gatilho de retomada — "continuar" (default) ou auto pelo fim-de-curso
MISSION_RESUME_TRIGGER: str = os.getenv("MISSION_RESUME_TRIGGER", "button")
