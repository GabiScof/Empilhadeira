"""Testes da vista de cima no robô real: /world-state e _real_world_state.

O componente Arena do frontend exige `world.{robot,arena,tags}`. No robô real
não há `/sim/world-state` (verdade-terreno do simulador), então o Arena cai para
`/world-state`, que deriva a pose do EKF + o mapa carregado.
"""

import importlib
from pathlib import Path

import app.config as config
import app.main as main
from app.state import SharedState
from app.world.map_schema import load_map
from app.world.world_model import WorldModel

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


def test_world_state_route_registered_always():
    """/world-state existe fora do modo SIM (é do robô real)."""
    config.SIM = False
    importlib.reload(main)
    app = main.create_app()
    paths = {r.path for r in app.routes}
    assert "/world-state" in paths


def test_real_world_state_shape_with_map():
    """Com mapa: forma que o Arena consome (world.robot/arena/tags + world_model)."""
    state = SharedState()
    state.load_world(WorldModel(load_map(MAPS_DIR / "corredor_pequeno.json")))

    ws = main._real_world_state(state)

    assert "world" in ws
    robot = ws["world"]["robot"]
    assert {"x_m", "y_m", "theta_rad", "theta_deg"} <= robot.keys()
    assert {"width_m", "height_m"} <= ws["world"]["arena"].keys()
    tag = ws["world"]["tags"][0]
    assert {"position_id", "x_m", "y_m", "yaw_deg"} <= tag.keys()
    # robô parte da pose inicial do mapa (via EKF)
    assert robot["x_m"] == state.ekf.x
    assert "world_model" in ws and "planned_path" in ws and "executed_trail" in ws


def test_real_world_state_without_map_omits_world():
    """Sem mapa: sem 'world' (Arena não desenha — precisa das dimensões da arena)."""
    ws = main._real_world_state(SharedState())
    assert "world" not in ws
    # mas ainda expõe ekf/mission/dock para os painéis numéricos
    assert "ekf" in ws and "mission" in ws and "dock" in ws
