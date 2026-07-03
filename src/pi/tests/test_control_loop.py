"""Testes do loop de controle de malha fechada (tasks/control_loop.py).

Cobre o achado #3: em AUTOMATICO, o controle roda continuamente a partir da
intenção do operador armazenada — NÃO precisa de stream contínuo de comandos.
Com a arquitetura antiga (controle no loop de recepção do WebSocket), um único
comando produzia um setpoint que congelava.
"""

import asyncio

from app.control.state_machine import StateMachine
from app.models import Command, Joystick, Mode, VisionState
from app.state import SharedState
from app.tasks.control_loop import control_loop


def _run_loop_for(state: SharedState, ticks: int, dt: float = 0.05):
    """Roda o control_loop por ~`ticks` iterações e devolve o setpoint final."""

    async def runner():
        task = asyncio.create_task(control_loop(state))
        await asyncio.sleep(ticks * dt)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return state.current_setpoint

    return asyncio.run(runner())


def test_auto_drives_from_single_command():
    """Um único comando AUTOMATICO + tag visível → setpoint contínuo não-nulo."""
    state = SharedState()
    # Operador clicou AUTOMATICO uma vez (como o frontend real faz).
    state.last_command = Command(modo=Mode.AUTOMATICO)
    state.state_machine.acknowledge()
    state.last_vision = VisionState(detectado=True, id=0, z_cm=30.0, x_cm=0.0, pitch_deg=0.0)

    sp = _run_loop_for(state, ticks=6)

    assert state.state_machine.mode == Mode.AUTOMATICO
    # v = Kz·(Z−Zref) > 0 → rodas girando para frente, sem novos comandos.
    assert abs(sp.w_esq) > 0.01 or abs(sp.w_dir) > 0.01


def test_manual_drives_from_single_joystick_command():
    """Um único comando MANUAL com joystick → setpoint contínuo não-nulo."""
    state = SharedState()
    state.last_command = Command(modo=Mode.MANUAL, joystick=Joystick(x=0.0, y=1.0))
    state.state_machine.acknowledge()

    sp = _run_loop_for(state, ticks=4)

    assert state.state_machine.mode == Mode.MANUAL
    assert sp.w_esq > 0.01 and sp.w_dir > 0.01


def test_no_command_stays_safe():
    """Sem operador (last_command None) → PARADO e rodas zeradas."""
    state = SharedState()
    state.last_command = None

    sp = _run_loop_for(state, ticks=3)

    assert state.state_machine.mode == Mode.PARADO
    assert sp.w_esq == 0.0 and sp.w_dir == 0.0


def test_tag_loss_in_loop_latches_parado():
    """Em AUTO, perder a tag durante o loop → PARADO travado (não oscila)."""
    state = SharedState()
    state.last_command = Command(modo=Mode.AUTOMATICO)
    state.state_machine.acknowledge()
    state.last_vision = VisionState(detectado=True, id=0, z_cm=30.0, x_cm=0.0, pitch_deg=0.0)

    # Alguns ticks navegando, depois some a tag.
    async def runner():
        task = asyncio.create_task(control_loop(state))
        await asyncio.sleep(0.15)
        assert state.state_machine.mode == Mode.AUTOMATICO
        state.last_vision = VisionState()  # tag perdida
        await asyncio.sleep(0.6)  # > TAG_LOST_FRAMES @ 20 Hz
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())

    assert state.state_machine.mode == Mode.PARADO
    assert state.state_machine.safety_latched
    assert state.current_setpoint.w_esq == 0.0
    assert isinstance(state.state_machine, StateMachine)
