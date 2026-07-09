"""Schemas Pydantic dos 4 contratos de interface do sistema.

Espelho Python de docs/serial-protocol.md. Mudanças devem ser refletidas
em firmware/src/protocol.* (C++) e frontend/src/types/contracts.ts (TS).

Convenções: rad/s (rodas), graus (ângulos), cm (distâncias), ms (timestamps).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Mode(StrEnum):
    """Modo de operação pedido pelo operador / estado da máquina de estados."""

    MANUAL = "MANUAL"
    AUTOMATICO = "AUTOMATICO"
    PARADO = "PARADO"


class ForkCommand(StrEnum):
    """Comando do garfo (canal independente, sempre manual)."""

    SUBIR = "subir"
    DESCER = "descer"
    PARAR = "parar"



# Contrato 1: Frontend → Pi (WebSocket)
class Joystick(BaseModel):
    """Posição do joystick virtual. Componentes em [-1, 1]. Só vale em MANUAL."""

    x: float = Field(0.0, ge=-1.0, le=1.0, description="Giro (ω), adimensional.")
    y: float = Field(0.0, ge=-1.0, le=1.0, description="Avanço (v), adimensional.")


class Command(BaseModel):
    """Comando enviado pelo frontend ao Pi via WebSocket.

    Campos:
        modo: estado desejado pelo operador.
        joystick: posição do joystick (ignorada fora de MANUAL).
        garfo: comando do garfo (vale nos dois modos).
        ts_ms: timestamp do cliente em ms (usado no watchdog de comando).
    """

    modo: Mode
    joystick: Joystick = Field(default_factory=Joystick)
    garfo: ForkCommand = ForkCommand.PARAR
    ts_ms: int = Field(0, ge=0)



# Contrato 2: Pi → Frontend · telemetria @20Hz (WebSocket)
class WheelSpeeds(BaseModel):
    """Velocidades angulares medidas das rodas, em rad/s."""

    esq: float = Field(description="Roda esquerda (rad/s).")
    dir: float = Field(description="Roda direita (rad/s).")


class ImuAngles(BaseModel):
    """Orientação filtrada (Kalman) em graus."""

    roll: float = Field(description="Roll (graus).")
    pitch: float = Field(description="Pitch (graus).")


class VisionState(BaseModel):
    """Saída da visão (detecção + pose da AprilTag). Campos null sem detecção."""

    detectado: bool = False
    id: int | None = None
    z_cm: float | None = Field(None, description="Distância ao alvo (cm).")
    x_cm: float | None = Field(None, description="Deslocamento lateral (cm).")
    pitch_deg: float | None = Field(None, description="Orientação relativa da tag (graus).")


class Battery(BaseModel):
    """Leituras de bateria. Campos null se o BMS não tiver leitura digital."""

    cel: float | None = Field(
        None, description="Tensão de célula. TODO(equipe): confirmar unidade (V?)."
    )
    i_a: float | None = Field(None, description="Corrente (A).")
    temp_c: float | None = Field(None, description="Temperatura (°C).")


class Telemetry(BaseModel):
    """Telemetria enviada pelo Pi ao frontend @20 Hz.

    Campos:
        estado: estado real da máquina de estados (não o pedido).
        rodas: velocidades medidas das rodas (rad/s).
        imu: roll/pitch filtrados (graus).
        visao: detecção e pose da tag.
        bateria: leituras do BMS (ou null).
        ts_ms: timestamp do Pi (ms).
    """

    estado: Mode
    rodas: WheelSpeeds
    imu: ImuAngles
    visao: VisionState = Field(default_factory=VisionState)
    bateria: Battery = Field(default_factory=Battery)
    ts_ms: int = Field(0, ge=0)
    parado_reason: str | None = Field(
        None,
        description="Razão da parada de segurança ativa (tag_loss, command_watchdog, "
        "ws_disconnect, force_stop). None se não há parada de segurança.",
    )
    nav_phase: str | None = Field(
        None,
        description="Fase atual da navegação automática (APPROACH, FACE, RETREAT). "
        "None fora do modo AUTOMATICO.",
    )
    ekf: EkfState | None = Field(None, description="Estado do EKF 2D.")
    mission: MissionInfo | None = Field(None, description="Estado da missão.")
    navigation: NavigationInfo | None = Field(None, description="Estado da navegação.")
    dock: DockInfo | None = Field(None, description="Estado do dock-to-tag.")
    detected_tags: list[DetectedTag] = Field(default_factory=list, description="Tags detectadas.")
    map_name: str | None = Field(None, description="Nome do mapa carregado.")



# Campos estendidos de telemetria
class EkfState(BaseModel):
    """Estado do EKF 2D para telemetria."""

    x_m: float = Field(description="Posição X estimada (m).")
    y_m: float = Field(description="Posição Y estimada (m).")
    theta_rad: float = Field(description="Heading estimado (rad).")
    theta_deg: float = Field(description="Heading estimado (graus).")
    covariance_trace: float = Field(description="Traço da covariância.")
    last_correction: str = Field(description="Fonte da última correção.")
    correction_count: int = Field(0, description="Nº de correções por tag.")
    ellipse_semi_major_m: float = Field(0.0, description="Semi-eixo maior da elipse.")
    ellipse_semi_minor_m: float = Field(0.0, description="Semi-eixo menor da elipse.")
    ellipse_angle_rad: float = Field(0.0, description="Ângulo da elipse.")


class MissionInfo(BaseModel):
    """Informação da missão para telemetria."""

    state: str = Field("IDLE", description="Estado da missão.")
    pick_position_id: str | None = None
    place_position_id: str | None = None
    fault_reason: str | None = None
    is_navigating: bool = False
    is_waiting_operator: bool = False
    elapsed_s: float = 0.0


class NavigationInfo(BaseModel):
    """Informação de navegação para telemetria."""

    executor_state: str = Field("IDLE", description="Estado do executor.")
    segment_index: int = 0
    total_segments: int = 0
    progress: float = 0.0
    current_segment_type: str | None = None


class DockInfo(BaseModel):
    """Estado do dock-to-tag (aproximação por segmentos a 1 tag) para telemetria.

    Inclui o detalhe fino do que o robô está fazendo AGORA (segmento atual,
    alvo, rodas comandadas) — feedback ao vivo para debug no frontend.
    """

    enabled: bool = Field(False, description="Se o dock está ligado (default True no boot, desligável via API).")
    state: str = Field("SEEKING", description="SEEKING / DOCKING / DONE / FAULT.")
    mode: str = Field("line_of_sight", description="Estratégia de alvo.")
    segments: int = Field(0, description="Segmentos na rota planejada.")
    detection_streak: int = Field(0, description="Detecções consecutivas (SEEKING).")
    min_detections: int = Field(3, description="Detecções exigidas para planejar.")
    goal: list[float] | None = Field(None, description="Alvo planejado [x_m, y_m, heading_rad].")
    plan: list[dict] = Field(default_factory=list, description="Rota completa planejada (segmentos).")
    planned_from: dict | None = Field(None, description="Leitura z_cm/x_cm usada no plano.")
    executor_state: str | None = Field(None, description="Estado do executor de segmentos.")
    seg_index: int = Field(0, description="Índice do segmento em execução.")
    seg_total: int = Field(0, description="Total de segmentos da rota.")
    seg_type: str | None = Field(None, description="Tipo do segmento atual (forward/turn).")
    seg_elapsed_s: float = Field(0.0, description="Tempo no segmento atual (s).")
    w_esq: float = Field(0.0, description="Roda esquerda comandada agora (rad/s).")
    w_dir: float = Field(0.0, description="Roda direita comandada agora (rad/s).")


class DetectedTag(BaseModel):
    """Tag detectada para telemetria.

    ``x_m``/``y_m`` é a posição da tag no MUNDO: a do mapa quando a tag é
    conhecida (``in_map=True``); senão, a posição ESTIMADA a partir da pose do
    EKF + leitura relativa (útil para conferir a colocação física das tags).
    ``z_cm``/``x_cm`` é a leitura relativa crua (convenção do projeto:
    x positivo = tag à ESQUERDA).
    """

    tag_id: int
    position_id: str | None = None
    x_m: float
    y_m: float
    quality: float = 1.0
    z_cm: float | None = None
    x_cm: float | None = None
    in_map: bool = True


Telemetry.model_rebuild()



# Contrato 3: Pi → ESP32 (UART)
class Setpoint(BaseModel):
    """Setpoint de velocidade das rodas + comando do garfo, enviado ao ESP32.

    Campos:
        w_esq: velocidade alvo da roda esquerda (rad/s).
        w_dir: velocidade alvo da roda direita (rad/s).
        garfo: comando do garfo, repassado direto ao motor.
    """

    w_esq: float = Field(description="Setpoint roda esquerda (rad/s).")
    w_dir: float = Field(description="Setpoint roda direita (rad/s).")
    garfo: ForkCommand = ForkCommand.PARAR



# Contrato 4: ESP32 → Pi (UART)
class Encoders(BaseModel):
    """Velocidades medidas pelos encoders, em rad/s."""

    esq: float = Field(description="Encoder esquerdo (rad/s).")
    dir: float = Field(description="Encoder direito (rad/s).")


class MpuRaw(BaseModel):
    """Leituras **cruas** do MPU-6050. A fusão (Kalman) é feita no Pi."""

    ax: float = Field(description="Aceleração X (m/s²).")
    ay: float = Field(description="Aceleração Y (m/s²).")
    az: float = Field(description="Aceleração Z (m/s²).")
    gx: float = Field(description="Velocidade angular X (graus/s).")
    gy: float = Field(description="Velocidade angular Y (graus/s).")
    gz: float = Field(description="Velocidade angular Z (graus/s).")
    temp_c: float = Field(description="Temperatura (°C).")


class Sensors(BaseModel):
    """Pacote de sensores enviado pelo ESP32 ao Pi.

    Campos:
        enc: velocidades dos encoders (rad/s).
        mpu: leituras cruas do MPU-6050.
        bms: leituras de bateria (mesmo formato de Battery) ou null.
    """

    enc: Encoders
    mpu: MpuRaw
    bms: Battery | None = None
