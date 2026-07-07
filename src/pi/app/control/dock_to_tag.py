"""Dock-to-tag: aproxima UMA tag avulsa por segmentos discretos (FORWARD/TURN).

Modo independente da missão, mirado no robô REAL. O robô vê uma tag, deriva um
ponto de parada em frente a ela (standoff) e planeja uma rota DIRETA de
segmentos — girar para ENCARAR o alvo e andar reto (TURN → FORWARD) —
executada pelo `SegmentExecutor`, a MESMA malha externa da missão, NÃO o
servo contínuo do navegador legado. A câmera é usada UMA vez (no plano);
a execução é 100% odometria/EKF.

**Diferença para o navegador legado (`NavigationController`):**
- Legado: recalcula (v, ω) todo frame a partir da tag → servo contínuo reativo.
- Este: planeja UMA vez ao ver a tag → executa a rota via EKF (odometria),
  igual à missão. Robusto a perder a tag do FOV durante uma curva (a missão
  desliga a segurança de tag-loss exatamente por isso — ver control_loop).

**Estratégias de alvo (config.DOCK_MODE):**
- "line_of_sight" (DEFAULT, real): para no standoff sobre a reta robô→tag, de
  frente para ela. Usa só z_cm/x_cm — NÃO depende de convenção de yaw.
- "tag_normal": quadra com a face da tag (pela normal). Depende do yaw da tag
  (config.DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD) — validar convenção antes de usar.

Fluxo (máquina de estados interna):
  SEEKING → (N detecções) → planeja → DOCKING → (rota concluída) → DONE
  qualquer → FAULT (timeout de segmento / alvo inválido)

[ref: docs/dock-to-tag.md]
"""

from __future__ import annotations

import logging
import math
from enum import StrEnum

from app import config
from app.control.path_planner import Segment, SegmentType
from app.control.segment_executor import ExecutorState, SegmentExecutor
from app.models import VisionState

logger = logging.getLogger(__name__)

# Re-visão no estado DONE: trajeto mínimo para justificar replanejar (tag
# nova/movida). Abaixo disto é a própria tag do estacionamento — ignora.
_REPLAN_MIN_TRAVEL_M: float = 0.10


def _wrap(a: float) -> float:
    """Normaliza ângulo para [-π, π]."""
    return math.atan2(math.sin(a), math.cos(a))


def tag_world_pose_from_vision(
    vision: VisionState,
    robot_x: float,
    robot_y: float,
    robot_theta: float,
    *,
    yaw_offset_rad: float = config.DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD,
) -> tuple[float, float, float] | None:
    """Pose da tag no mundo (x_m, y_m, yaw_rad) a partir da leitura relativa.

    Inverte a mesma geometria de `vision_loop._feed_ekf_from_detections`
    (que conhece a tag e resolve o robô) para conhecer o robô e resolver a tag.

    Args:
        vision: leitura da visão (z_cm/x_cm/pitch_deg no frame do robô).
        robot_x, robot_y: pose atual do robô estimada pelo EKF (m).
        robot_theta: heading atual do robô (rad).
        yaw_offset_rad: offset de convenção pitch_deg → yaw do tag (ver config).

    Returns:
        (tag_x_m, tag_y_m, tag_yaw_rad) ou None se sem detecção/dados.
    """
    if not vision.detectado or vision.z_cm is None or vision.x_cm is None:
        return None

    z_m = vision.z_cm / 100.0
    x_m = vision.x_cm / 100.0
    pitch_deg = vision.pitch_deg or 0.0

    dist = math.hypot(z_m, x_m)
    bearing_world = robot_theta + math.atan2(x_m, z_m)
    tag_x = robot_x + dist * math.cos(bearing_world)
    tag_y = robot_y + dist * math.sin(bearing_world)
    tag_yaw = _wrap(robot_theta + math.radians(pitch_deg) + yaw_offset_rad)

    return tag_x, tag_y, tag_yaw


def dock_goal_line_of_sight(
    vision: VisionState,
    robot_x: float,
    robot_y: float,
    robot_theta: float,
    standoff_m: float,
) -> tuple[float, float, float] | None:
    """Alvo na LINHA DE VISÃO até a tag — o padrão robusto para o robô real.

    Para o robô ``standoff_m`` antes da tag, sobre a reta robô→tag, de frente
    para ela. Usa APENAS ``z_cm``/``x_cm`` (distância + rumo), que são bem
    definidos e idênticos aos que o navegador legado já usa no hardware. **Não**
    depende de ``pitch_deg`` nem da convenção de yaw da tag.

    Não quadra com a face da tag (para isso use ``dock_goal_face_normal``): para
    onde estiver, na direção em que a tag foi vista.

    Returns:
        (goal_x_m, goal_y_m, goal_heading_rad) ou None se sem detecção.
    """
    if not vision.detectado or vision.z_cm is None or vision.x_cm is None:
        return None

    z_m = vision.z_cm / 100.0
    x_m = vision.x_cm / 100.0
    dist = math.hypot(z_m, x_m)
    bearing_world = robot_theta + math.atan2(x_m, z_m)
    reach = max(dist - standoff_m, 0.0)

    goal_x = robot_x + reach * math.cos(bearing_world)
    goal_y = robot_y + reach * math.sin(bearing_world)
    goal_heading = _wrap(bearing_world)  # de frente para a tag
    return goal_x, goal_y, goal_heading


def dock_goal_face_normal(
    tag_x: float, tag_y: float, tag_yaw: float, standoff_m: float
) -> tuple[float, float, float]:
    """Ponto de parada quadrado com a FACE da tag (aproxima pela normal).

    Standoff ao longo da normal externa da tag; heading apontando de volta
    para a tag. Espelha `WorldModel.tag_approach_pose_m_rad`. Depende do yaw da
    tag → só use com a convenção validada (ver config.DOCK_MODE).

    Returns:
        (goal_x_m, goal_y_m, goal_heading_rad).
    """
    goal_x = tag_x + standoff_m * math.cos(tag_yaw)
    goal_y = tag_y + standoff_m * math.sin(tag_yaw)
    goal_heading = _wrap(tag_yaw + math.pi)
    return goal_x, goal_y, goal_heading


class DockState(StrEnum):
    """Estados da máquina de dock-to-tag."""
    SEEKING = "SEEKING"    # aguardando detecção estável para planejar
    DOCKING = "DOCKING"    # executando a rota de segmentos
    DONE = "DONE"          # chegou ao standoff — robô parado
    FAULT = "FAULT"        # falha (timeout de segmento, alvo inválido)


class TagDocker:
    """Estaciona o robô em frente a uma tag via segmentos discretos.

    Isolado da missão: usa o PRÓPRIO `SegmentExecutor` (não compartilha o da
    missão). Só age quando `config.DOCK_TO_TAG_ENABLED` está ligado e o ramo
    AUTOMATICO-sem-missão o invoca (ver control_loop).
    """

    def __init__(
        self,
        standoff_m: float = config.DOCK_STANDOFF_M,
        min_detections: int = config.DOCK_MIN_DETECTIONS,
        mode: str = config.DOCK_MODE,
    ) -> None:
        self._standoff_m = standoff_m
        self._min_detections = max(1, min_detections)
        self._mode = mode
        self._executor = SegmentExecutor(
            wheel_radius_m=config.WHEEL_RADIUS_M,
            wheelbase_m=config.WHEELBASE_M,
            max_v_ms=config.MAX_LINEAR_SPEED_MS,
            max_omega_rads=config.MAX_ANGULAR_SPEED_RADS,
        )
        self._state = DockState.SEEKING
        self._detection_streak = 0
        self._segments: list[Segment] = []
        self._goal: tuple[float, float, float] | None = None
        # Telemetria fina (debug ao vivo no frontend):
        self._last_w: tuple[float, float] = (0.0, 0.0)
        self._planned_from: dict | None = None  # leitura z/x usada no plano

    @property
    def state(self) -> DockState:
        return self._state

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def standoff_m(self) -> float:
        return self._standoff_m

    def configure(
        self, *, mode: str | None = None, standoff_m: float | None = None
    ) -> None:
        """Reconfigura estratégia/standoff e volta a SEEKING (chamado pela API)."""
        if mode is not None:
            self._mode = mode
        if standoff_m is not None:
            self._standoff_m = standoff_m
        self.reset()

    @property
    def is_docking(self) -> bool:
        """True enquanto executa a rota — control_loop suprime tag-loss aqui."""
        return self._state == DockState.DOCKING

    @property
    def segments(self) -> list[Segment]:
        return self._segments

    @property
    def goal(self) -> tuple[float, float, float] | None:
        return self._goal

    def reset(self) -> None:
        """Volta a SEEKING e limpa o plano (chamado ao sair de AUTOMATICO)."""
        self._executor.reset()
        self._state = DockState.SEEKING
        self._detection_streak = 0
        self._segments = []
        self._goal = None
        self._last_w = (0.0, 0.0)
        self._planned_from = None

    def step(
        self,
        vision: VisionState,
        robot_x: float,
        robot_y: float,
        robot_theta: float,
        dt: float,
    ) -> tuple[float, float]:
        """Avança o dock um tick e retorna (ω_esq, ω_dir) em rad/s.

        Args:
            vision: leitura atual da visão (para planejar em SEEKING).
            robot_x, robot_y, robot_theta: pose atual do EKF (m, m, rad).
            dt: intervalo desde o último tick (s).
        """
        if self._state == DockState.FAULT:
            self._last_w = (0.0, 0.0)
            return 0.0, 0.0

        if self._state == DockState.DONE:
            # RE-VISÃO (2026-07-07): estacionado, continua olhando. Se uma tag
            # aparecer pedindo um trajeto novo relevante (> _REPLAN_MIN_TRAVEL
            # — tag nova colocada, tag movida, robô empurrado), volta a
            # planejar sozinho, sem precisar sair do AUTOMATICO.
            self._last_w = (0.0, 0.0)
            self._seek(
                vision, robot_x, robot_y, robot_theta,
                min_travel_m=_REPLAN_MIN_TRAVEL_M,
            )
            return 0.0, 0.0

        if self._state == DockState.SEEKING:
            self._last_w = self._seek(vision, robot_x, robot_y, robot_theta)
            return self._last_w

        # DOCKING: executa a rota planejada via EKF.
        if self._executor.state == ExecutorState.ROUTE_DONE:
            self._state = DockState.DONE
            logger.info("Dock concluído — robô em frente à tag")
            self._last_w = (0.0, 0.0)
            return 0.0, 0.0
        if self._executor.state == ExecutorState.TIMEOUT:
            self._state = DockState.FAULT
            logger.warning("Dock FAULT — timeout de segmento")
            self._last_w = (0.0, 0.0)
            return 0.0, 0.0

        self._last_w = self._executor.step(
            x=robot_x, y=robot_y, theta=robot_theta, dt=dt
        )
        return self._last_w

    def _seek(
        self,
        vision: VisionState,
        robot_x: float,
        robot_y: float,
        robot_theta: float,
        *,
        min_travel_m: float = 0.0,
    ) -> tuple[float, float]:
        """Acumula detecções e, ao estabilizar, planeja a rota. Fica parado.

        ``min_travel_m`` > 0 (re-visão no DONE): só replaneja se o trajeto
        novo for relevante — evita loop de replanejamento pela própria tag
        onde ele acabou de estacionar.
        """
        if not vision.detectado:
            self._detection_streak = 0
            return 0.0, 0.0

        self._detection_streak += 1
        if self._detection_streak < self._min_detections:
            return 0.0, 0.0

        goal = self._compute_goal(vision, robot_x, robot_y, robot_theta)
        if goal is None:
            self._detection_streak = 0
            return 0.0, 0.0

        if min_travel_m > 0.0:
            travel = math.hypot(goal[0] - robot_x, goal[1] - robot_y)
            if travel < min_travel_m:
                self._detection_streak = 0
                return 0.0, 0.0
            logger.info(
                "Dock re-visão: situação mudou (trajeto novo de %.2f m) — replanejando",
                travel,
            )
        self._goal = goal
        self._planned_from = {
            "z_cm": round(vision.z_cm, 1) if vision.z_cm is not None else None,
            "x_cm": round(vision.x_cm, 1) if vision.x_cm is not None else None,
        }

        # Passinho Manhattan NO FRAME DO ROBÔ (2026-07-07): avança, gira 90°,
        # avança, gira e encara. (O plan_route Manhattan da missão alinha nos
        # eixos do MAPA — na bancada o frame é arbitrário e o robô girava para
        # direções sem relação com a tag; aqui as pernas são relativas ao rumo
        # atual do robô.)
        segments = self._plan_steps(robot_x, robot_y, robot_theta, goal)
        self._segments = segments
        self._executor.load_route(segments)

        if self._executor.state == ExecutorState.ROUTE_DONE:
            # Já estava no standoff (rota vazia) — nada a fazer.
            self._state = DockState.DONE
            logger.info("Dock: já em frente à tag (rota vazia)")
        else:
            self._state = DockState.DOCKING
            logger.info(
                "Dock[%s]: alvo (%.2f, %.2f, %.1f°) — %d segmentos",
                self._mode,
                goal[0], goal[1], math.degrees(goal[2]), len(segments),
            )
        return 0.0, 0.0

    @staticmethod
    def _plan_steps(
        x: float, y: float, theta: float, goal: tuple[float, float, float]
    ) -> list[Segment]:
        """Manhattan NO FRAME DO ROBÔ — o "passinho" clássico, sem o bug do frame.

        Pernas alinhadas ao rumo ATUAL do robô (não aos eixos do mapa, que na
        bancada são arbitrários e faziam o robô girar para direções sem relação
        com a tag): AVANÇO (componente à frente) → GIRO ±90° → AVANÇO
        (componente lateral) → GIRO final para encarar o alvo. Pernas < 1 cm
        somem; alvo atrás do robô cai no fallback direto (girar e ir).
        """
        gx, gy, gheading = goal
        dxw, dyw = gx - x, gy - y
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        # Projeção no frame do robô: dz à frente, dlat positivo = esquerda.
        dz = dxw * cos_t + dyw * sin_t
        dlat = -dxw * sin_t + dyw * cos_t

        segments: list[Segment] = []

        if dz < -0.01:
            # Alvo atrás (raro — FOV da câmera é frontal): rota direta.
            bearing = math.atan2(dyw, dxw)
            turn1 = _wrap(bearing - theta)
            if abs(turn1) > 0.02:
                segments.append(Segment(
                    type=SegmentType.TURN, value=turn1,
                    target_x=x, target_y=y, target_heading=bearing,
                ))
            dist = math.hypot(dxw, dyw)
            segments.append(Segment(
                type=SegmentType.FORWARD, value=dist,
                target_x=gx, target_y=gy, target_heading=bearing,
            ))
            heading = bearing
        else:
            heading = theta
            px, py = x, y
            if dz > 0.01:
                px += dz * cos_t
                py += dz * sin_t
                segments.append(Segment(
                    type=SegmentType.FORWARD, value=dz,
                    target_x=px, target_y=py, target_heading=heading,
                ))
            if abs(dlat) > 0.01:
                quarter = math.pi / 2 * (1.0 if dlat > 0 else -1.0)
                heading = _wrap(heading + quarter)
                segments.append(Segment(
                    type=SegmentType.TURN, value=quarter,
                    target_x=px, target_y=py, target_heading=heading,
                ))
                segments.append(Segment(
                    type=SegmentType.FORWARD, value=abs(dlat),
                    target_x=gx, target_y=gy, target_heading=heading,
                ))

        final_turn = _wrap(gheading - heading)
        if abs(final_turn) > 0.02:
            segments.append(Segment(
                type=SegmentType.TURN, value=final_turn,
                target_x=gx, target_y=gy, target_heading=gheading,
            ))
        return segments

    def _compute_goal(
        self, vision: VisionState, robot_x: float, robot_y: float, robot_theta: float
    ) -> tuple[float, float, float] | None:
        """Deriva o alvo conforme a estratégia (config.DOCK_MODE)."""
        if self._mode == "tag_normal":
            tag_pose = tag_world_pose_from_vision(vision, robot_x, robot_y, robot_theta)
            if tag_pose is None:
                return None
            tag_x, tag_y, tag_yaw = tag_pose
            return dock_goal_face_normal(tag_x, tag_y, tag_yaw, self._standoff_m)

        # Default robusto: linha de visão (não depende de convenção de yaw).
        return dock_goal_line_of_sight(
            vision, robot_x, robot_y, robot_theta, self._standoff_m
        )

    def to_dict(self) -> dict:
        """Serialização para telemetria/debug — o que o robô está fazendo AGORA."""
        ex = self._executor.to_dict()
        seg = ex.get("current_segment") or {}
        return {
            "state": self._state.value,
            "mode": self._mode,
            "detection_streak": self._detection_streak,
            "min_detections": self._min_detections,
            "segments": len(self._segments),
            "goal": (
                [round(v, 3) for v in self._goal] if self._goal else None
            ),
            "plan": [s.to_dict() for s in self._segments],
            "planned_from": self._planned_from,
            "executor_state": ex.get("state"),
            "seg_index": ex.get("segment_index", 0),
            "seg_total": ex.get("total_segments", 0),
            "seg_type": seg.get("type"),
            "seg_elapsed_s": ex.get("elapsed_s", 0.0),
            "w_esq": round(self._last_w[0], 2),
            "w_dir": round(self._last_w[1], 2),
        }
