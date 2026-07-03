"""Tarefa de controle: missão + navegação + máquina de estados → setpoint, a 20 Hz.

Em MANUAL: joystick → cinemática → setpoint.
Em AUTOMATICO com missão ativa: missão SM → planejador → executor → setpoint.
Em AUTOMATICO sem missão (legado): navegador antigo → setpoint.

[ref: Seção 2 e 5 do mega-prompt]
"""

from __future__ import annotations

import asyncio
import logging
import time

from app import config
from app.control.kinematics import joystick_to_twist, twist_to_wheel_speeds
from app.control.path_planner import plan_route
from app.control.segment_executor import ExecutorState
from app.models import ForkCommand, Mode, Setpoint, VisionState
from app.state import SharedState

logger = logging.getLogger(__name__)


def _propose_wheel_speeds_manual(
    joystick_x: float, joystick_y: float
) -> tuple[float, float]:
    """Modo MANUAL: joystick → (w_esq, w_dir) em rad/s."""
    v, omega = joystick_to_twist(joystick_x, joystick_y)
    return twist_to_wheel_speeds(v, omega)


def _propose_wheel_speeds_mission(state: SharedState, dt: float) -> tuple[float, float]:
    """Modo AUTOMATICO com missão: executor → (w_esq, w_dir) em rad/s."""
    mission = state.mission
    executor = state.segment_executor

    if not mission.is_active:
        return 0.0, 0.0

    if mission.is_waiting_operator:
        return 0.0, 0.0

    if mission.is_navigating:
        if executor.state == ExecutorState.IDLE:
            target = mission.get_current_target()
            if target is None:
                mission.fault("Alvo de navegação não encontrado no mapa")
                return 0.0, 0.0

            goal_x, goal_y, goal_heading = target
            segments = plan_route(
                start_x=state.ekf.x,
                start_y=state.ekf.y,
                start_heading=state.ekf.theta,
                goal_x=goal_x,
                goal_y=goal_y,
                goal_heading=goal_heading,
                world=state.world_model,
            )
            state.planned_path = segments
            executor.load_route(segments)
            logger.info("Rota planejada: %d segmentos", len(segments))

        if executor.state == ExecutorState.ROUTE_DONE:
            mission.notify_route_done()
            executor.reset()
            return 0.0, 0.0

        if executor.state == ExecutorState.TIMEOUT:
            mission.fault("Timeout no segmento de navegação")
            executor.reset()
            return 0.0, 0.0

        w_esq, w_dir = executor.step(
            x=state.ekf.x,
            y=state.ekf.y,
            theta=state.ekf.theta,
            dt=dt,
        )

        trail_point = (state.ekf.x, state.ekf.y)
        if not state.executed_trail or state.executed_trail[-1] != trail_point:
            state.executed_trail.append(trail_point)
            if len(state.executed_trail) > 2000:
                state.executed_trail = state.executed_trail[-1000:]

        return w_esq, w_dir

    return 0.0, 0.0


def _propose_wheel_speeds_legacy(
    vision: VisionState, state: SharedState
) -> tuple[float, float]:
    """Modo AUTOMATICO legado (sem missão): navegador antigo."""
    if not vision.detectado:
        return 0.0, 0.0
    v, omega = state.navigator.compute(
        z_cm=vision.z_cm or 0.0,
        x_cm=vision.x_cm or 0.0,
        pitch_deg=vision.pitch_deg or 0.0,
    )
    return twist_to_wheel_speeds(v, omega)


async def control_loop(state: SharedState) -> None:
    """Loop de controle de malha fechada a `config.CONTROL_HZ`."""
    logger.info("Control loop iniciado (%.0f Hz)", config.CONTROL_HZ)
    interval = 1.0 / config.CONTROL_HZ
    last_time = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            dt = now - last_time
            last_time = now
            current_time_ms = int(time.time() * 1000)

            async with state.lock:
                command = state.last_command
                vision = state.last_vision

            if command is None:
                if state.mission.is_active:
                    requested_mode = Mode.AUTOMATICO
                else:
                    requested_mode = Mode.PARADO
                joystick_x = joystick_y = 0.0
                garfo = ForkCommand.PARAR
            else:
                requested_mode = command.modo
                joystick_x = command.joystick.x
                joystick_y = command.joystick.y
                garfo = command.garfo

            # Propor velocidades conforme o modo
            if requested_mode == Mode.MANUAL:
                w_esq, w_dir = _propose_wheel_speeds_manual(joystick_x, joystick_y)
            elif requested_mode == Mode.AUTOMATICO:
                if state.mission.is_active:
                    w_esq, w_dir = _propose_wheel_speeds_mission(state, dt)
                else:
                    w_esq, w_dir = _propose_wheel_speeds_legacy(vision, state)
            else:
                w_esq, w_dir = 0.0, 0.0

            # Missão ativa: EKF cuida da localização, tag-loss de segurança
            # não se aplica (tags podem sair do FOV durante turns normais).
            if state.mission.is_active:
                vision_for_sm = VisionState(detectado=True)
                if state.state_machine.safety_latched:
                    state.state_machine.acknowledge()
            else:
                vision_for_sm = vision

            mode, w_esq, w_dir, garfo = state.state_machine.step(
                requested_mode=requested_mode,
                vision=vision_for_sm,
                garfo=garfo,
                current_time_ms=current_time_ms,
                w_esq=w_esq,
                w_dir=w_dir,
            )

            if state.state_machine.check_command_watchdog(current_time_ms):
                w_esq, w_dir = 0.0, 0.0
                logger.warning("Watchdog de comando disparou → PARADO")

            await state.update_setpoint(Setpoint(w_esq=w_esq, w_dir=w_dir, garfo=garfo))

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Control loop cancelado")
