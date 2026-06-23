"""Ponto de entrada do backend do Pi.

Em SIM=1: carrega mapa, cria mundo parametrizado, emulador, visão sintética.
Em REAL: serial real, câmera real.

Rotas sim: /sim/reset-pose, /sim/inject-fault, /sim/world-state, /sim/debug-dump,
          /sim/load-map, /sim/list-maps, /sim/mission/start, /sim/mission/continue,
          /sim/mission/reset.

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import config
from app.state import SharedState
from app.world.world_model import WorldModel
from app.world.map_schema import load_map

logger = logging.getLogger(__name__)

_state: SharedState | None = None
_emulator = None
_world = None
_synthetic_vision = None
_fault_injector = None


class PoseResetRequest(BaseModel):
    x: float
    y: float
    theta: float


class FaultRequest(BaseModel):
    fault_type: str
    active: bool = True
    value: float | None = None
    value2: float | None = None


class MissionStartRequest(BaseModel):
    pick_id: str | None = None
    place_id: str | None = None


def _resolve_map_path(map_name: str) -> Path:
    """Resolve o caminho de um mapa pelo nome."""
    maps_dir = config.MAPS_DIR
    path = maps_dir / f"{map_name}.json"
    if path.exists():
        return path
    raise FileNotFoundError(f"Mapa '{map_name}' não encontrado em {maps_dir}")


def _load_world_model(map_name: str) -> WorldModel:
    """Carrega o WorldModel de um mapa pelo nome."""
    path = _resolve_map_path(map_name)
    return WorldModel.from_file(path)


def _setup_sim_world(state: SharedState, world_model: WorldModel):
    """Configura o mundo simulado a partir do WorldModel.

    Armazena referências em ``state`` para hot-swap nas tasks asyncio.
    """
    global _world, _emulator, _synthetic_vision, _fault_injector

    from app.sim.fault_injector import FaultInjector
    from app.sim.firmware_emulator import FirmwareEmulator
    from app.sim.synthetic_vision import SyntheticVision
    from app.sim.world import SimWorld

    _world = SimWorld(world_model=world_model, robot_model=state.robot_model)
    _emulator = FirmwareEmulator(world=_world)
    _synthetic_vision = SyntheticVision()
    _fault_injector = FaultInjector()
    _fault_injector.bind(_emulator, _synthetic_vision, _world)

    state.sim_emulator = _emulator
    state.sim_world = _world
    state.sim_vision = _synthetic_vision
    state.load_world(world_model)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida: inicia tarefas no startup, cancela no shutdown."""
    global _state

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    _state = SharedState()
    tasks: list[asyncio.Task] = []

    if config.SIM:
        logger.info("Modo SIMULAÇÃO (SIM=1)")

        try:
            world_model = _load_world_model(config.DEFAULT_MAP)
            _setup_sim_world(_state, world_model)
            logger.info("Mapa carregado: %s", config.DEFAULT_MAP)
        except FileNotFoundError as e:
            logger.warning("Mapa padrão não encontrado: %s — usando fallback", e)
            from app.sim.firmware_emulator import FirmwareEmulator
            from app.sim.synthetic_vision import SyntheticVision
            from app.sim.world import SimWorld
            from app.sim.fault_injector import FaultInjector
            global _world, _emulator, _synthetic_vision, _fault_injector
            _world = SimWorld()
            _emulator = FirmwareEmulator(world=_world)
            _synthetic_vision = SyntheticVision()
            _fault_injector = FaultInjector()
            _fault_injector.bind(_emulator, _synthetic_vision, _world)
            _state.sim_emulator = _emulator
            _state.sim_world = _world
            _state.sim_vision = _synthetic_vision

        from app.tasks.serial_loop import serial_loop_sim
        from app.tasks.vision_loop import SimVisionSource, vision_loop

        vision_source = SimVisionSource(_state)
        tasks.append(asyncio.create_task(serial_loop_sim(_state)))
        tasks.append(asyncio.create_task(vision_loop(_state, vision_source)))
    else:
        logger.info("Modo REAL (hardware)")
        from app.tasks.serial_loop import serial_loop_real
        from app.tasks.vision_loop import RealVisionSource, vision_loop

        try:
            world_model = _load_world_model(config.DEFAULT_MAP)
            _state.load_world(world_model)
            logger.info("Mapa carregado (modo real): %s", config.DEFAULT_MAP)
        except FileNotFoundError:
            logger.warning("Mapa não encontrado para modo real — continuando sem mapa")

        try:
            vision_source = RealVisionSource()
            tasks.append(asyncio.create_task(vision_loop(_state, vision_source)))
        except Exception as e:
            logger.error("Visão real indisponível — seguindo sem visão: %s", e)

        try:
            tasks.append(asyncio.create_task(serial_loop_real(_state)))
        except Exception as e:
            logger.error("Serial real indisponível — seguindo sem serial: %s", e)

    from app.tasks.control_loop import control_loop

    tasks.append(asyncio.create_task(control_loop(_state)))

    logger.info("Tarefas asyncio iniciadas (%d)", len(tasks))

    yield

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Tarefas asyncio finalizadas")


def create_app() -> FastAPI:
    app = FastAPI(title="Empilhadeira Pi", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        from app.tasks.websocket_handler import websocket_endpoint

        if _state is None:
            await websocket.close()
            return
        await websocket_endpoint(websocket, _state)

    if config.SIM:
        _register_sim_routes(app)

    _register_mission_routes(app)
    _register_map_routes(app)

    return app


def _register_map_routes(app: FastAPI) -> None:
    """Rotas para gerenciamento de mapas."""

    @app.get("/maps/list")
    async def list_maps():
        maps_dir = config.MAPS_DIR
        if not maps_dir.exists():
            return {"maps": []}
        maps = []
        for f in sorted(maps_dir.glob("*.json")):
            try:
                m = load_map(f)
                maps.append({
                    "name": m.name,
                    "file": f.stem,
                    "arena": {"width_m": m.arena.width_m, "height_m": m.arena.height_m},
                    "tags": len(m.tags),
                    "has_graph": m.waypoints is not None and len(m.waypoints) > 0,
                })
            except Exception:
                pass
        return {"maps": maps}

    @app.post("/maps/load/{map_name}")
    async def load_map_route(map_name: str):
        if _state is None:
            return {"ok": False, "error": "server not ready"}
        try:
            world_model = _load_world_model(map_name)
            if config.SIM:
                _setup_sim_world(_state, world_model)
            else:
                _state.load_world(world_model)
            return {"ok": True, "map": world_model.to_dict()}
        except FileNotFoundError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/maps/current")
    async def current_map():
        if _state is None or _state.world_model is None:
            return {"ok": False, "map": None}
        return {"ok": True, "map": _state.world_model.to_dict()}


def _register_mission_routes(app: FastAPI) -> None:
    """Rotas para controle da missão."""

    @app.post("/mission/start")
    async def start_mission(req: MissionStartRequest):
        if _state is None:
            return {"ok": False, "error": "server not ready"}
        if _state.world_model is None:
            return {"ok": False, "error": "nenhum mapa carregado"}
        ok = _state.mission.start_mission(
            _state.world_model,
            pick_id=req.pick_id,
            place_id=req.place_id,
        )
        return {"ok": ok, "mission": _state.mission.to_dict()}

    @app.post("/mission/continue")
    async def continue_mission():
        if _state is None:
            return {"ok": False}
        ok = _state.mission.operator_continue()
        return {"ok": ok, "mission": _state.mission.to_dict()}

    @app.post("/mission/reset")
    async def reset_mission():
        if _state is None:
            return {"ok": False}
        _state.mission.reset()
        _state.segment_executor.reset()
        _state.planned_path = []
        return {"ok": True, "mission": _state.mission.to_dict()}

    @app.get("/mission/state")
    async def mission_state():
        if _state is None:
            return {"ok": False}
        return {"ok": True, "mission": _state.mission.to_dict()}


def _register_sim_routes(app: FastAPI) -> None:
    """Rotas de API para o modo simulação (/demo)."""

    @app.post("/sim/reset-pose")
    async def reset_pose(req: PoseResetRequest):
        if _world is not None:
            _world.reset_pose(req.x, req.y, req.theta)
        if _state is not None:
            _state.ekf.reset(req.x, req.y, req.theta)
        return {"ok": True}

    @app.post("/sim/inject-fault")
    async def inject_fault(req: FaultRequest):
        if _fault_injector is None:
            return {"ok": False, "error": "not in sim mode"}

        if req.fault_type == "serial_drop":
            _fault_injector.inject_serial_drop(req.active)
        elif req.fault_type == "tag_hidden":
            _fault_injector.inject_tag_hidden(req.active)
        elif req.fault_type == "wheel_slip":
            esq = req.value if req.value is not None else 1.0
            dir_ = req.value2 if req.value2 is not None else 1.0
            _fault_injector.inject_wheel_slip(esq, dir_)
        elif req.fault_type == "battery_saturated":
            _fault_injector.inject_battery_saturated(req.active)
        elif req.fault_type == "vision_blur":
            _fault_injector.inject_vision_blur(req.value or 0.0)
        elif req.fault_type == "vision_drop":
            _fault_injector.inject_vision_drop(req.value or 0.0)
        elif req.fault_type == "encoder_noise":
            _fault_injector.inject_encoder_noise(req.value or 0.05)
        elif req.fault_type == "gyro_drift":
            _fault_injector.inject_gyro_drift(req.value or 0.001)
        elif req.fault_type == "clear_all":
            _fault_injector.clear_all()

        return {"ok": True, "state": _fault_injector.get_state()}

    @app.get("/sim/world-state")
    async def world_state():
        result: dict = {}
        if _world is not None:
            result["world"] = _world.get_state()
        if _emulator is not None:
            from app.sim.firmware_emulator import FirmwareEmulator
            if isinstance(_emulator, FirmwareEmulator):
                result["fork_height"] = round(_emulator.fork_height, 2)
                result["fork_at_top"] = _emulator.fork_at_top()
                result["fork_at_bottom"] = _emulator.fork_at_bottom()
                result["pid"] = _emulator.pid_state()
        if _fault_injector is not None:
            result["faults"] = _fault_injector.get_state()
        if _state is not None:
            result["ekf"] = _state.ekf.to_dict()
            if _state.world_model:
                result["world_model"] = _state.world_model.to_dict()
            result["mission"] = _state.mission.to_dict()
            result["executor"] = _state.segment_executor.to_dict()
            result["planned_path"] = [s.to_dict() for s in _state.planned_path]
            result["executed_trail"] = _state.executed_trail[-200:]
        return result

    @app.get("/sim/debug-dump")
    async def debug_dump():
        from app.sim.firmware_emulator import FirmwareEmulator

        dump: dict = {"ts_server_ms": int(__import__("time").time() * 1000)}

        dump["config"] = {
            k: v
            for k, v in vars(config).items()
            if not k.startswith("_") and isinstance(v, (int, float, str, bool, tuple))
        }

        if _world is not None:
            dump["world"] = _world.get_state()

        if _emulator is not None and isinstance(_emulator, FirmwareEmulator):
            dump["emulator"] = {
                "setpoint_w_esq": round(_emulator.setpoint_w_esq, 4),
                "setpoint_w_dir": round(_emulator.setpoint_w_dir, 4),
                "setpoint_garfo": str(_emulator.setpoint_garfo),
                "setpoint_valid": _emulator.setpoint_valid,
                "measured_esq": round(_emulator.measured_esq, 4),
                "measured_dir": round(_emulator.measured_dir, 4),
                "fork_height": round(_emulator.fork_height, 2),
            }

        if _fault_injector is not None:
            dump["faults"] = _fault_injector.get_state()

        if _state is not None:
            async with _state.lock:
                dump["state_machine"] = {
                    "mode": str(_state.state_machine.mode),
                    "safety_latched": _state.state_machine.safety_latched,
                    "last_safety_reason": _state.state_machine.last_safety_reason,
                }
                dump["ekf"] = _state.ekf.to_dict()
                dump["mission"] = _state.mission.to_dict()
                dump["navigator"] = {
                    "using_fallback": _state.navigator.using_fallback,
                }
                if _state.last_command is not None:
                    dump["last_command"] = _state.last_command.model_dump()
                else:
                    dump["last_command"] = None
                dump["last_vision"] = _state.last_vision.model_dump()
                dump["last_imu"] = _state.last_imu.model_dump()
                dump["current_setpoint"] = _state.current_setpoint.model_dump()

            telemetry = await _state.snapshot_telemetry()
            dump["telemetry"] = telemetry.model_dump()

        return dump


def main() -> None:
    import uvicorn
    uvicorn.run(
        "app.main:create_app",
        host=config.WS_HOST,
        port=config.WS_PORT,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
