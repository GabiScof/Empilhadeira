"""Ponto de entrada do backend do Pi: cria as 3 tarefas asyncio concorrentes.

Backend assíncrono único (FastAPI + asyncio). Sobe três tarefas que compartilham
`SharedState`:
- WebSocket Handler (comando/telemetria com o frontend)
- Vision Loop (AprilTag → pose)
- Serial Loop (setpoint/sensores com o ESP32)

Em modo SIM=1, usa emulador do firmware e visão sintética em vez de hardware real.

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import config
from app.state import SharedState


class PoseResetRequest(BaseModel):
    x: float
    y: float
    theta: float


class FaultRequest(BaseModel):
    fault_type: str
    active: bool = True
    value: float | None = None
    value2: float | None = None


logger = logging.getLogger(__name__)

_state: SharedState | None = None
_emulator = None
_world = None
_synthetic_vision = None
_fault_injector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida: inicia tarefas no startup, cancela no shutdown."""
    global _state, _emulator, _world, _synthetic_vision, _fault_injector

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    _state = SharedState()
    tasks: list[asyncio.Task] = []

    if config.SIM:
        logger.info("Modo SIMULAÇÃO (SIM=1)")
        from app.sim.fault_injector import FaultInjector
        from app.sim.firmware_emulator import FirmwareEmulator
        from app.sim.synthetic_vision import SyntheticVision
        from app.sim.world import SimWorld
        from app.tasks.serial_loop import serial_loop_sim
        from app.tasks.vision_loop import SimVisionSource, vision_loop

        _world = SimWorld()
        _emulator = FirmwareEmulator(world=_world)
        _synthetic_vision = SyntheticVision()
        _fault_injector = FaultInjector()
        _fault_injector.bind(_emulator, _synthetic_vision, _world)

        vision_source = SimVisionSource(_synthetic_vision, _world)
        tasks.append(asyncio.create_task(serial_loop_sim(_state, _emulator)))
        tasks.append(asyncio.create_task(vision_loop(_state, vision_source)))
    else:
        logger.info("Modo REAL (hardware)")
        from app.tasks.serial_loop import serial_loop_real
        from app.tasks.vision_loop import RealVisionSource, vision_loop

        vision_source = RealVisionSource()
        tasks.append(asyncio.create_task(serial_loop_real(_state)))
        tasks.append(asyncio.create_task(vision_loop(_state, vision_source)))

    from app.tasks.control_loop import control_loop

    tasks.append(asyncio.create_task(control_loop(_state)))

    logger.info("Tarefas asyncio iniciadas (%d)", len(tasks))

    yield

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Tarefas asyncio finalizadas")


def create_app() -> FastAPI:
    """Cria a aplicação FastAPI e registra as rotas/WebSocket.

    Returns:
        Instância de FastAPI configurada.
    """
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

    return app


def _register_sim_routes(app: FastAPI) -> None:
    """Registra rotas de API para o modo simulação (/demo)."""

    @app.post("/sim/reset-pose")
    async def reset_pose(req: PoseResetRequest):
        if _world is not None:
            _world.reset_pose(req.x, req.y, req.theta)
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
        if _fault_injector is not None:
            result["faults"] = _fault_injector.get_state()
        return result


def main() -> None:
    """Entrada de linha de comando: roda o servidor (uvicorn)."""
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
