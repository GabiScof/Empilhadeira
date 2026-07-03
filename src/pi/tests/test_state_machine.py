"""Testes da máquina de estados: transições, segurança, watchdog."""

from app import config
from app.control.state_machine import StateMachine
from app.models import ForkCommand, Mode, VisionState


def _vision(detected: bool = True) -> VisionState:
    if detected:
        return VisionState(detectado=True, id=0, z_cm=20.0, x_cm=0.0, pitch_deg=0.0)
    return VisionState()


def test_initial_state_parado():
    """Estado inicial é PARADO."""
    sm = StateMachine()
    assert sm.mode == Mode.PARADO


def test_parado_to_manual():
    """Operador pode ir de PARADO para MANUAL."""
    sm = StateMachine()
    mode, w_e, w_d, g = sm.step(Mode.MANUAL, _vision(), ForkCommand.PARAR, 1000)
    assert mode == Mode.MANUAL


def test_parado_to_automatico():
    """Operador pode ir de PARADO para AUTOMATICO."""
    sm = StateMachine()
    mode, *_ = sm.step(Mode.AUTOMATICO, _vision(), ForkCommand.PARAR, 1000)
    assert mode == Mode.AUTOMATICO


def test_manual_to_automatico():
    """Operador pode ir de MANUAL para AUTOMATICO."""
    sm = StateMachine()
    sm.step(Mode.MANUAL, _vision(), ForkCommand.PARAR, 1000)
    mode, *_ = sm.step(Mode.AUTOMATICO, _vision(), ForkCommand.PARAR, 1100)
    assert mode == Mode.AUTOMATICO


def test_automatico_to_manual():
    """Operador pode ir de AUTOMATICO para MANUAL."""
    sm = StateMachine()
    sm.step(Mode.AUTOMATICO, _vision(), ForkCommand.PARAR, 1000)
    mode, *_ = sm.step(Mode.MANUAL, _vision(), ForkCommand.PARAR, 1100)
    assert mode == Mode.MANUAL


def test_parado_zeroes_wheels():
    """Em PARADO, rodas devem ser zeradas."""
    sm = StateMachine()
    mode, w_e, w_d, g = sm.step(
        Mode.PARADO, _vision(), ForkCommand.PARAR, 1000, w_esq=5.0, w_dir=5.0
    )
    assert mode == Mode.PARADO
    assert w_e == 0.0
    assert w_d == 0.0


def test_tag_loss_triggers_parado():
    """Perder a tag por >TAG_LOST_FRAMES frames em AUTO → PARADO."""
    sm = StateMachine()
    sm.step(Mode.AUTOMATICO, _vision(), ForkCommand.PARAR, 1000)

    for i in range(config.TAG_LOST_FRAMES + 1):
        mode, w_e, w_d, g = sm.step(
            Mode.AUTOMATICO, _vision(False), ForkCommand.PARAR, 1100 + i * 50
        )

    assert mode == Mode.PARADO
    assert w_e == 0.0
    assert w_d == 0.0


def test_tag_recovery_resets_counter():
    """Reencontrar a tag reseta o contador de perda."""
    sm = StateMachine()
    sm.step(Mode.AUTOMATICO, _vision(), ForkCommand.PARAR, 1000)

    for i in range(config.TAG_LOST_FRAMES - 1):
        sm.step(Mode.AUTOMATICO, _vision(False), ForkCommand.PARAR, 1100 + i * 50)

    mode, *_ = sm.step(Mode.AUTOMATICO, _vision(True), ForkCommand.PARAR, 2000)
    assert mode == Mode.AUTOMATICO


def test_exit_parado_requires_explicit_action():
    """Sair de PARADO exige ação explícita (enviar MANUAL ou AUTOMATICO)."""
    sm = StateMachine()
    mode, *_ = sm.step(Mode.PARADO, _vision(), ForkCommand.PARAR, 1000)
    assert mode == Mode.PARADO

    mode, *_ = sm.step(Mode.MANUAL, _vision(), ForkCommand.PARAR, 1100)
    assert mode == Mode.MANUAL


def test_safety_stop_latches_under_continuous_request():
    """Parada de segurança (perda de tag) trava: re-propor AUTO não reativa."""
    sm = StateMachine()
    sm.step(Mode.AUTOMATICO, _vision(), ForkCommand.PARAR, 1000)

    # Perde a tag → PARADO + latch.
    for i in range(config.TAG_LOST_FRAMES + 1):
        sm.step(Mode.AUTOMATICO, _vision(False), ForkCommand.PARAR, 1100 + i * 50)
    assert sm.mode == Mode.PARADO
    assert sm.safety_latched

    # O loop de controle re-propõe AUTOMATICO todo tick (tag de volta), mas o latch
    # mantém PARADO — sem oscilação.
    for i in range(20):
        mode, *_ = sm.step(Mode.AUTOMATICO, _vision(True), ForkCommand.PARAR, 2000 + i * 50)
        assert mode == Mode.PARADO


def test_acknowledge_releases_safety_latch():
    """acknowledge() (ação explícita do operador) libera o latch e permite reativar."""
    sm = StateMachine()
    sm.step(Mode.AUTOMATICO, _vision(), ForkCommand.PARAR, 1000)
    for i in range(config.TAG_LOST_FRAMES + 1):
        sm.step(Mode.AUTOMATICO, _vision(False), ForkCommand.PARAR, 1100 + i * 50)
    assert sm.mode == Mode.PARADO and sm.safety_latched

    sm.acknowledge()
    assert not sm.safety_latched
    mode, *_ = sm.step(Mode.AUTOMATICO, _vision(True), ForkCommand.PARAR, 5000)
    assert mode == Mode.AUTOMATICO


def test_force_stop():
    """force_stop() leva a PARADO de qualquer estado."""
    sm = StateMachine()
    sm.step(Mode.MANUAL, _vision(), ForkCommand.PARAR, 1000)
    sm.force_stop()
    assert sm.mode == Mode.PARADO
    assert sm.safety_latched


def test_garfo_passes_through():
    """Comando do garfo passa direto independente do modo."""
    sm = StateMachine()
    sm.step(Mode.MANUAL, _vision(), ForkCommand.PARAR, 1000)
    mode, w_e, w_d, garfo = sm.step(
        Mode.MANUAL, _vision(), ForkCommand.SUBIR, 1100, w_esq=1.0, w_dir=1.0
    )
    assert garfo == ForkCommand.SUBIR


def test_command_watchdog():
    """Watchdog de comando no MANUAL: sem comando por muito tempo → PARADO."""
    sm = StateMachine()
    sm.step(Mode.MANUAL, _vision(), ForkCommand.PARAR, 1000, w_esq=1.0, w_dir=1.0)
    sm.update_command_time(1000)

    triggered = sm.check_command_watchdog(1000 + config.COMMAND_WATCHDOG_MS + 100)
    assert triggered
    assert sm.mode == Mode.PARADO
