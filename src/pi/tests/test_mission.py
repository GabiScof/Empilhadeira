"""Testes da máquina de estados de missão.

Cobre:
- Fluxo completo IDLE → ... → DONE.
- Pausa de garra: AT_PICK/AT_PLACE esperam "continuar" do operador.
- Sorteio de targets.
- FAULT em caso de erro.
"""

from pathlib import Path

import pytest

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


class TestMissionSM:
    def _make_world(self, map_name="corredor_pequeno"):
        from app.world.map_schema import load_map
        from app.world.world_model import WorldModel

        m = load_map(MAPS_DIR / f"{map_name}.json")
        return WorldModel(m)

    def test_start_mission(self):
        from app.mission.mission_sm import MissionSM, MissionState

        sm = MissionSM()
        world = self._make_world()
        ok = sm.start_mission(world)
        assert ok
        assert sm.state == MissionState.GO_TO_PICK
        assert sm.pick_position_id is not None
        assert sm.place_position_id is not None
        assert sm.pick_position_id != sm.place_position_id

    def test_forced_targets(self):
        from app.mission.mission_sm import MissionSM, MissionState

        sm = MissionSM()
        world = self._make_world()
        ok = sm.start_mission(world, pick_id="P1", place_id="P2")
        assert ok
        assert sm.pick_position_id == "P1"
        assert sm.place_position_id == "P2"

    def test_at_pick_waits(self):
        from app.mission.mission_sm import MissionSM, MissionState

        sm = MissionSM()
        world = self._make_world()
        sm.start_mission(world, pick_id="P1", place_id="P2")
        sm.notify_route_done()  # chegou no pick
        assert sm.state == MissionState.AT_PICK
        assert sm.is_waiting_operator

    def test_continue_from_at_pick(self):
        from app.mission.mission_sm import MissionSM, MissionState

        sm = MissionSM()
        world = self._make_world()
        sm.start_mission(world, pick_id="P1", place_id="P2")
        sm.notify_route_done()  # → AT_PICK
        ok = sm.operator_continue()  # → GO_TO_PLACE
        assert ok
        assert sm.state == MissionState.GO_TO_PLACE

    def test_full_mission_flow(self):
        from app.mission.mission_sm import MissionSM, MissionState

        sm = MissionSM()
        world = self._make_world()
        sm.start_mission(world, pick_id="P1", place_id="P2")
        assert sm.state == MissionState.GO_TO_PICK
        sm.notify_route_done()
        assert sm.state == MissionState.AT_PICK
        sm.operator_continue()
        assert sm.state == MissionState.GO_TO_PLACE
        sm.notify_route_done()
        assert sm.state == MissionState.AT_PLACE
        sm.operator_continue()
        assert sm.state == MissionState.GO_HOME
        sm.notify_route_done()
        assert sm.state == MissionState.DONE

    def test_fault(self):
        from app.mission.mission_sm import MissionSM, MissionState

        sm = MissionSM()
        world = self._make_world()
        sm.start_mission(world)
        sm.fault("test error")
        assert sm.state == MissionState.FAULT
        assert sm.fault_reason == "test error"

    def test_reset(self):
        from app.mission.mission_sm import MissionSM, MissionState

        sm = MissionSM()
        world = self._make_world()
        sm.start_mission(world)
        sm.reset()
        assert sm.state == MissionState.IDLE

    def test_too_few_tags(self):
        from app.mission.mission_sm import MissionSM, MissionState
        from app.world.map_schema import ArenaMap
        from app.world.world_model import WorldModel

        m = ArenaMap.model_validate({
            "name": "tiny",
            "arena": {"width_m": 1.0, "height_m": 1.0},
            "start_pose": {"x_m": 0.1, "y_m": 0.1, "theta_deg": 0},
            "home_pose": {"x_m": 0.1, "y_m": 0.1, "theta_deg": 0},
            "tags": [{"position_id": "P1", "x_m": 0.5, "y_m": 0.5, "yaw_deg": 0}],
        })
        wm = WorldModel(m)
        sm = MissionSM()
        ok = sm.start_mission(wm)
        assert not ok
        assert sm.state == MissionState.FAULT

    def test_get_current_target(self):
        from app.mission.mission_sm import MissionSM

        sm = MissionSM()
        world = self._make_world()
        sm.start_mission(world, pick_id="P1", place_id="P2")
        target = sm.get_current_target()
        assert target is not None
        x, y, theta = target
        assert isinstance(x, float)

    def test_to_dict(self):
        from app.mission.mission_sm import MissionSM

        sm = MissionSM()
        d = sm.to_dict()
        assert "state" in d
        assert d["state"] == "IDLE"
