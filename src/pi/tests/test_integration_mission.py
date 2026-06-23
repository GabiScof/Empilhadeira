"""Testes de integração: missão completa com simulador.

Cobre:
- Missão completa em arena pequena → DONE.
- Missão completa em arena grande com grafo → DONE.
- Pausa de garra nos estados AT_PICK/AT_PLACE.
- Missão com visão degradada (apenas odometria) → demonstra drift.
"""

import math
from pathlib import Path

import pytest

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


def _run_mission_sim(map_name, pick_id=None, place_id=None, max_steps=2000, vision_drop=False):
    """Roda uma missão completa em simulação pura (sem asyncio)."""
    from app.control.ekf import PoseEKF
    from app.control.path_planner import plan_route
    from app.control.segment_executor import ExecutorState, SegmentExecutor
    from app.mission.mission_sm import MissionSM, MissionState
    from app.sim.synthetic_vision import SyntheticVision
    from app.sim.world import SimWorld
    from app.world.map_schema import load_map
    from app.world.robot_model import RobotModel
    from app.world.world_model import WorldModel

    arena_map = load_map(MAPS_DIR / f"{map_name}.json")
    world_model = WorldModel(arena_map)
    robot_model = RobotModel()

    sim_world = SimWorld(world_model=world_model, robot_model=robot_model)
    vision = SyntheticVision()
    if vision_drop:
        vision.set_drop_prob(1.0)  # sem visão

    ekf = PoseEKF(*world_model.start_pose)
    mission = MissionSM()
    executor = SegmentExecutor(
        wheel_radius_m=robot_model.wheel_radius_m,
        wheelbase_m=robot_model.wheelbase_m,
    )

    ok = mission.start_mission(world_model, pick_id=pick_id, place_id=place_id)
    assert ok, "Falha ao iniciar missão"

    dt = 0.05
    states_visited = set()

    for step_i in range(max_steps):
        states_visited.add(mission.state)

        if mission.state == MissionState.DONE:
            break

        if mission.state == MissionState.FAULT:
            break

        if mission.is_waiting_operator:
            mission.operator_continue()
            continue

        if mission.is_navigating:
            if executor.state == ExecutorState.IDLE:
                target = mission.get_current_target()
                if target is None:
                    mission.fault("Alvo não encontrado")
                    break
                gx, gy, gh = target
                segments = plan_route(ekf.x, ekf.y, ekf.theta, gx, gy, gh, world=world_model)
                executor.load_route(segments)

            if executor.state == ExecutorState.ROUTE_DONE:
                mission.notify_route_done()
                executor.reset()
                continue

            if executor.state == ExecutorState.TIMEOUT:
                mission.fault("Timeout")
                break

            w_l, w_r = executor.step(ekf.x, ekf.y, ekf.theta, dt)
        else:
            w_l, w_r = 0.0, 0.0

        sim_world.step(w_l, w_r, dt)

        v, omega = robot_model.forward_kinematics(w_l, w_r)
        ekf.predict(w_l, w_r, omega, dt, robot_model.wheel_radius_m, robot_model.wheelbase_m)

        if not vision_drop:
            detections = vision.compute_all(sim_world)
            for det in detections:
                tag_spec = world_model.get_tag_by_position_id(det.position_id)
                if tag_spec:
                    dist = math.sqrt(det.z_m**2 + det.x_m**2)
                    bearing_rel = math.atan2(det.x_m, det.z_m)
                    bearing_world = ekf.theta + bearing_rel
                    obs_x = tag_spec.x_m - dist * math.cos(bearing_world)
                    obs_y = tag_spec.y_m - dist * math.sin(bearing_world)
                    obs_theta = tag_spec.yaw_rad - det.yaw_rad - math.pi
                    ekf.correct_apriltag(obs_x, obs_y, obs_theta, det.quality)

    return mission.state, states_visited, ekf


class TestIntegrationMission:
    def test_mission_corredor_pequeno(self):
        state, visited, ekf = _run_mission_sim("corredor_pequeno", "P1", "P2")
        assert state.value == "DONE", f"Missão terminou em {state}, visitou {visited}"
        assert "AT_PICK" in {s.value for s in visited}
        assert "AT_PLACE" in {s.value for s in visited}

    def test_mission_arena_media(self):
        state, visited, ekf = _run_mission_sim("arena_media", "P1", "P3")
        assert state.value == "DONE", f"Missão terminou em {state}"

    def test_mission_arena_grande_com_grafo(self):
        # Arena grande precisa de mais passos para concluir GO_HOME → DONE
        state, visited, ekf = _run_mission_sim(
            "arena_grande_com_grafo", "P1", "P3", max_steps=5000
        )
        assert state.value == "DONE", f"Missão terminou em {state}"

    def test_mission_corredor_6tags(self):
        state, visited, ekf = _run_mission_sim("corredor_6tags", "L1", "R2", max_steps=5000)
        assert state.value == "DONE", f"Missão terminou em {state}"
        assert "AT_PICK" in {s.value for s in visited}
        assert "AT_PLACE" in {s.value for s in visited}

    def test_mission_with_vision_drop_drifts(self):
        """Sem visão, a odometria pura acumula drift — pode não completar."""
        state, visited, ekf = _run_mission_sim(
            "corredor_pequeno", "P1", "P2", max_steps=2000, vision_drop=True
        )
        # Com odometria pura pode ou não completar, mas a covariância deve ser alta
        assert ekf.covariance_trace > 0.01  # drift acumulado
