"""Testes do dock-to-tag: geometria, planejamento por segmentos e SM.

Modo default = "line_of_sight" (alvo do robô REAL): usa só z_cm/x_cm, não
depende de convenção de yaw. O modo "tag_normal" (quadra com a face) usa o yaw
e é validado aqui contra a verdade-terreno do SIM (convenção do SIM = offset π).
"""

import math

from app import config
from app.control.dock_to_tag import (
    DockState,
    TagDocker,
    _wrap,
    dock_goal_face_normal,
    dock_goal_line_of_sight,
    tag_world_pose_from_vision,
)
from app.control.path_planner import SegmentType
from app.models import VisionState
from app.sim.synthetic_vision import SyntheticVision

_SIM_YAW_OFFSET = math.pi  # convenção de yaw da visão sintética do SIM


def _clean_vision() -> SyntheticVision:
    """Visão sintética com ruído zerado — verdade-terreno determinística."""
    sv = SyntheticVision(seed=1)
    sv._noise_std_m = 0.0
    sv._noise_std_rad = 0.0
    return sv


# ---------------------------------------------------------------------------
# Geometria — reconstrução da pose da tag validada contra o SIM
# ---------------------------------------------------------------------------
def test_reconstruct_tag_pose_straight_ahead():
    """Robô olhando a tag de frente: reconstrução casa com a verdade do SIM."""
    # Robô em (100,150)cm olhando -y; tag em (100,50)cm apontando +y (para o robô).
    sv = _clean_vision()
    vision = sv.compute(
        robot_x=100.0, robot_y=150.0, robot_theta=-math.pi / 2,
        tag_x=100.0, tag_y=50.0, tag_theta=math.pi / 2,
    )
    assert vision.detectado

    tag = tag_world_pose_from_vision(
        vision, robot_x=1.0, robot_y=1.5, robot_theta=-math.pi / 2,
        yaw_offset_rad=_SIM_YAW_OFFSET,
    )
    assert tag is not None
    tx, ty, tyaw = tag
    assert tx == 1.0
    assert abs(ty - 0.5) < 1e-6
    assert abs(_ang(tyaw - math.pi / 2)) < 1e-6


def test_reconstruct_tag_pose_off_axis():
    """Tag lateral dentro do FOV: posição e yaw reconstruídos corretamente."""
    sv = _clean_vision()
    # Robô em (100,150)cm olhando -y; tag deslocada em x.
    vision = sv.compute(
        robot_x=100.0, robot_y=150.0, robot_theta=-math.pi / 2,
        tag_x=130.0, tag_y=60.0, tag_theta=math.pi / 2,
    )
    assert vision.detectado

    tag = tag_world_pose_from_vision(
        vision, robot_x=1.0, robot_y=1.5, robot_theta=-math.pi / 2
    )
    assert tag is not None
    tx, ty, _ = tag
    assert abs(tx - 1.30) < 1e-6
    assert abs(ty - 0.60) < 1e-6


def test_face_normal_goal_is_standoff_in_front():
    """tag_normal: alvo standoff sobre a normal da tag, de frente para ela."""
    # Tag em (1,0) apontando +x (normal para +x); standoff 0.15.
    gx, gy, gh = dock_goal_face_normal(
        tag_x=1.0, tag_y=0.0, tag_yaw=0.0, standoff_m=0.15
    )
    assert abs(gx - 1.15) < 1e-9
    assert abs(gy) < 1e-9
    # Heading aponta de volta para a tag (-x → π).
    assert abs(_ang(gh - math.pi)) < 1e-9


def test_line_of_sight_goal_stops_short_facing_tag():
    """line_of_sight: para standoff antes da tag, sobre a reta robô→tag."""
    # Robô na origem olhando +x; tag 1 m à frente, 0.5 m à esquerda.
    vision = VisionState(detectado=True, z_cm=100.0, x_cm=50.0, pitch_deg=0.0)
    goal = dock_goal_line_of_sight(vision, 0.0, 0.0, 0.0, standoff_m=0.15)
    assert goal is not None
    gx, gy, gh = goal
    dist = math.hypot(1.0, 0.5)
    bearing = math.atan2(0.5, 1.0)
    reach = dist - 0.15
    assert abs(gx - reach * math.cos(bearing)) < 1e-9
    assert abs(gy - reach * math.sin(bearing)) < 1e-9
    assert abs(_ang(gh - bearing)) < 1e-9


def test_line_of_sight_ignores_yaw_convention():
    """line_of_sight não depende de pitch_deg: mesmo alvo para qualquer pitch."""
    a = dock_goal_line_of_sight(
        VisionState(detectado=True, z_cm=100.0, x_cm=0.0, pitch_deg=0.0),
        0.0, 0.0, 0.0, standoff_m=0.15,
    )
    b = dock_goal_line_of_sight(
        VisionState(detectado=True, z_cm=100.0, x_cm=0.0, pitch_deg=137.0),
        0.0, 0.0, 0.0, standoff_m=0.15,
    )
    assert a == b


def test_no_detection_returns_none():
    assert tag_world_pose_from_vision(VisionState(), 0, 0, 0) is None
    assert dock_goal_line_of_sight(VisionState(), 0, 0, 0, 0.15) is None


# ---------------------------------------------------------------------------
# Planejamento — segmentos discretos (avança / gira 90°)
# ---------------------------------------------------------------------------
def test_plans_single_forward_when_aligned():
    """Tag reta à frente → uma rota FORWARD só, sem curvas."""
    docker = TagDocker(standoff_m=0.15, min_detections=1, mode="line_of_sight")
    # Robô na origem olhando +x; tag 1m à frente.
    vision = VisionState(detectado=True, z_cm=100.0, x_cm=0.0, pitch_deg=0.0)
    docker.step(vision, robot_x=0.0, robot_y=0.0, robot_theta=0.0, dt=0.05)

    assert docker.state == DockState.DOCKING
    assert len(docker.segments) == 1
    assert docker.segments[0].type == SegmentType.FORWARD
    # Para a 0.85m (1.0m − standoff 0.15m).
    assert abs(docker.segments[0].value - 0.85) < 1e-6


def test_plans_local_manhattan_when_lateral():
    """Tag na diagonal → passinho Manhattan NO FRAME DO ROBÔ.

    Avança a componente à frente, gira 90° seco, avança a lateral, e gira
    para ENCARAR a tag. (As pernas são relativas ao rumo atual do robô —
    não aos eixos do mapa, que na bancada são arbitrários.)
    """
    docker = TagDocker(standoff_m=0.15, min_detections=1, mode="line_of_sight")
    # Tag à frente e à esquerda: z=1m, x=0.5m → bearing = atan2(0.5, 1.0).
    vision = VisionState(detectado=True, z_cm=100.0, x_cm=50.0, pitch_deg=0.0)
    docker.step(vision, robot_x=0.0, robot_y=0.0, robot_theta=0.0, dt=0.05)

    assert docker.state == DockState.DOCKING
    bearing = math.atan2(0.5, 1.0)
    reach = math.hypot(1.0, 0.5) - 0.15
    goal_x = reach * math.cos(bearing)
    goal_y = reach * math.sin(bearing)

    types = [s.type for s in docker.segments]
    assert types == [
        SegmentType.FORWARD,   # componente à frente
        SegmentType.TURN,      # 90° seco (o passinho clássico)
        SegmentType.FORWARD,   # componente lateral
        SegmentType.TURN,      # encarar a tag
    ]
    assert abs(docker.segments[0].value - goal_x) < 1e-6
    assert abs(abs(docker.segments[1].value) - math.pi / 2) < 1e-6
    assert abs(docker.segments[2].value - goal_y) < 1e-6
    # O giro final deixa o robô ENCARANDO a tag.
    assert abs(_wrap(docker.segments[3].target_heading - bearing)) < 1e-6


def test_done_replans_when_situation_changes():
    """RE-VISÃO: estacionado (DONE), uma tag pedindo trajeto novo → replaneja.

    E a própria tag do estacionamento (trajeto ~0) NÃO dispara loop.
    """
    docker = TagDocker(standoff_m=0.15, min_detections=1, mode="line_of_sight")
    # Doca na tag a 20 cm (trajeto de 5 cm) e força DONE consumindo a rota.
    vision = VisionState(detectado=True, z_cm=20.0, x_cm=0.0, pitch_deg=0.0)
    docker.step(vision, robot_x=0.0, robot_y=0.0, robot_theta=0.0, dt=0.05)
    assert docker.state == DockState.DOCKING
    # Simula chegada: pose exatamente no alvo → executor conclui.
    gx, gy, gh = docker.goal
    for _ in range(10):
        docker.step(vision, robot_x=gx, robot_y=gy, robot_theta=gh, dt=0.05)
        if docker.state == DockState.DONE:
            break
    assert docker.state == DockState.DONE

    # Mesma tag ainda a ~15 cm (standoff): trajeto ~0 → continua DONE.
    near = VisionState(detectado=True, z_cm=15.0, x_cm=0.0, pitch_deg=0.0)
    for _ in range(3):
        docker.step(near, robot_x=gx, robot_y=gy, robot_theta=gh, dt=0.05)
    assert docker.state == DockState.DONE

    # Situação mudou: tag (nova/movida) a 80 cm → replaneja sozinho.
    far = VisionState(detectado=True, z_cm=80.0, x_cm=0.0, pitch_deg=0.0)
    docker.step(far, robot_x=gx, robot_y=gy, robot_theta=gh, dt=0.05)
    assert docker.state == DockState.DOCKING


def test_tag_normal_mode_uses_face_normal():
    """mode='tag_normal' roteia pela normal da face (alvo != line_of_sight)."""
    docker = TagDocker(standoff_m=0.15, min_detections=1, mode="tag_normal")
    vision = VisionState(detectado=True, z_cm=100.0, x_cm=0.0, pitch_deg=0.0)
    docker.step(vision, robot_x=0.0, robot_y=0.0, robot_theta=0.0, dt=0.05)
    assert docker.state == DockState.DOCKING
    # Com offset default (0.0), a tag "aponta" +x, então o standoff fica ALÉM da
    # tag (1.15), distinto do line_of_sight (0.85) — prova que o ramo mudou.
    assert docker.goal is not None
    assert abs(docker.goal[0] - 1.15) < 1e-6


# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------
def test_debounce_requires_min_detections():
    docker = TagDocker(standoff_m=0.15, min_detections=3, mode="line_of_sight")
    vision = VisionState(detectado=True, z_cm=100.0, x_cm=0.0, pitch_deg=0.0)

    for _ in range(2):
        w = docker.step(vision, 0.0, 0.0, 0.0, dt=0.05)
        assert w == (0.0, 0.0)
        assert docker.state == DockState.SEEKING

    docker.step(vision, 0.0, 0.0, 0.0, dt=0.05)
    assert docker.state == DockState.DOCKING


def test_lost_detection_resets_streak():
    docker = TagDocker(standoff_m=0.15, min_detections=3, mode="line_of_sight")
    seen = VisionState(detectado=True, z_cm=100.0, x_cm=0.0, pitch_deg=0.0)
    docker.step(seen, 0.0, 0.0, 0.0, dt=0.05)
    docker.step(VisionState(), 0.0, 0.0, 0.0, dt=0.05)  # perdeu
    docker.step(seen, 0.0, 0.0, 0.0, dt=0.05)
    # Streak reiniciou: ainda não planejou.
    assert docker.state == DockState.SEEKING


def test_seeking_is_stationary():
    docker = TagDocker(standoff_m=0.15, min_detections=1, mode="line_of_sight")
    w = docker.step(VisionState(), 0.0, 0.0, 0.0, dt=0.05)
    assert w == (0.0, 0.0)


def test_reaches_done_when_at_goal():
    docker = TagDocker(standoff_m=0.15, min_detections=1, mode="line_of_sight")
    vision = VisionState(detectado=True, z_cm=100.0, x_cm=0.0, pitch_deg=0.0)
    docker.step(vision, robot_x=0.0, robot_y=0.0, robot_theta=0.0, dt=0.05)
    assert docker.state == DockState.DOCKING
    goal_x = docker.goal[0]

    # Robô já no alvo: dois ticks para o executor concluir e o dock ir a DONE.
    docker.step(vision, robot_x=goal_x, robot_y=0.0, robot_theta=0.0, dt=0.05)
    w = docker.step(vision, robot_x=goal_x, robot_y=0.0, robot_theta=0.0, dt=0.05)
    assert docker.state == DockState.DONE
    assert w == (0.0, 0.0)


def test_reset_returns_to_seeking():
    docker = TagDocker(standoff_m=0.15, min_detections=1, mode="line_of_sight")
    vision = VisionState(detectado=True, z_cm=100.0, x_cm=0.0, pitch_deg=0.0)
    docker.step(vision, 0.0, 0.0, 0.0, dt=0.05)
    assert docker.state == DockState.DOCKING
    docker.reset()
    assert docker.state == DockState.SEEKING
    assert docker.segments == []
    assert docker.goal is None


def test_enabled_by_default():
    """Guarda-corpo: o default COMMITADO é LIGADO (decisão de 2026-07-07).

    O env desligado a cada restart derrubava o AUTOMATICO no caminho legado
    ("tag perdida" imediato na bancada). O dock é o modo padrão do
    AUTOMATICO-sem-missão; desligável em runtime via POST /dock/disable.
    Valor hardcoded (sem env) — este teste protege contra regressão ao getenv.
    """
    assert config.DOCK_TO_TAG_ENABLED is True


# ---------------------------------------------------------------------------
# Integração — dock de malha fechada no simulador (robô REALMENTE chega)
# ---------------------------------------------------------------------------
def test_closed_loop_dock_reaches_tag():
    """Robô vê a tag, planeja segmentos discretos e ESTACIONA no standoff.

    Malha fechada completa: visão sintética → docker → sim → EKF (com correção
    de tags mapeadas). Prova que o robô chega ~2 cm do alvo, não só que planeja.
    """
    from pathlib import Path

    from app.control.ekf import PoseEKF
    from app.sim.world import SimWorld
    from app.world.map_schema import load_map
    from app.world.robot_model import RobotModel
    from app.world.world_model import WorldModel

    maps_dir = Path(__file__).resolve().parent.parent / "maps"
    wm = WorldModel(load_map(maps_dir / "corredor_pequeno.json"))
    rm = RobotModel()
    sim = SimWorld(world_model=wm, robot_model=rm)
    vision = SyntheticVision()
    ekf = PoseEKF(*wm.start_pose)
    docker = TagDocker(standoff_m=0.15, min_detections=3, mode="line_of_sight")

    dt = 0.05
    for _ in range(2000):
        vs = vision.compute_legacy(sim)
        w_l, w_r = docker.step(vs, ekf.x, ekf.y, ekf.theta, dt)
        if docker.state in (DockState.DONE, DockState.FAULT):
            break
        sim.step(w_l, w_r, dt)
        _v, omega = rm.forward_kinematics(w_l, w_r)
        ekf.predict(w_l, w_r, omega, dt, rm.wheel_radius_m, rm.wheelbase_m)
        for det in vision.compute_all(sim):
            ts = wm.get_tag_by_position_id(det.position_id)
            if ts:
                dist = math.hypot(det.z_m, det.x_m)
                bw = ekf.theta + math.atan2(det.x_m, det.z_m)
                ekf.correct_apriltag(
                    ts.x_m - dist * math.cos(bw),
                    ts.y_m - dist * math.sin(bw),
                    ts.yaw_rad - det.yaw_rad - math.pi,
                    det.quality,
                )

    assert docker.state == DockState.DONE
    assert docker.goal is not None
    rx, ry, _ = sim._pose_m()
    gx, gy, _ = docker.goal
    assert math.hypot(rx - gx, ry - gy) < 0.05  # chegou a <5 cm do standoff
    # E a rota é DIRETA (2026-07-07): girar para encarar → andar reto,
    # sem "L" de Manhattan (no máximo TURN, FORWARD e um TURN final).
    # Passinho Manhattan local: no máx. 2 avanços; giros intermediários de
    # 90° secos; o giro FINAL encara a tag (ângulo livre).
    types = [s.type for s in docker.segments]
    assert types.count(SegmentType.FORWARD) <= 2 and len(types) <= 4
    for s in docker.segments[:-1]:
        if s.type == SegmentType.TURN:
            assert abs(abs(s.value) - math.pi / 2) < 0.05


# ---------------------------------------------------------------------------
# Controle pelo frontend — runtime flag, configure, rotas REST, telemetria
# ---------------------------------------------------------------------------
def test_configure_changes_mode_and_resets():
    docker = TagDocker(standoff_m=0.15, min_detections=1, mode="line_of_sight")
    vision = VisionState(detectado=True, z_cm=100.0, x_cm=0.0, pitch_deg=0.0)
    docker.step(vision, 0.0, 0.0, 0.0, dt=0.05)  # entra em DOCKING
    docker.configure(mode="tag_normal", standoff_m=0.25)
    assert docker.mode == "tag_normal"
    assert docker.standoff_m == 0.25
    assert docker.state == DockState.SEEKING  # configure reseta


def test_telemetry_includes_dock():
    """O estado do dock chega ao frontend pela telemetria (canal do robô real)."""
    import asyncio

    from app.state import SharedState

    state = SharedState()
    state.dock_enabled = True
    state.docker.configure(mode="line_of_sight")
    tel = asyncio.run(state.snapshot_telemetry())
    assert tel.dock is not None
    assert tel.dock.enabled is True
    assert tel.dock.mode == "line_of_sight"
    assert tel.dock.state == "SEEKING"


def test_dock_routes_registered_and_take_json_body():
    """/dock/enable|disable|state existem e /dock/enable aceita corpo JSON."""
    import importlib

    import app.config as cfg
    import app.main as main

    cfg.SIM = False
    importlib.reload(main)
    app = main.create_app()

    paths = {r.path for r in app.routes}
    assert {"/dock/enable", "/dock/disable", "/dock/state"} <= paths

    post = app.openapi()["paths"]["/dock/enable"]["post"]
    assert "requestBody" in post  # corpo JSON, não query param (evita 422)


def _ang(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))
