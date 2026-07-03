"""Testes da visão sintética: pose correta, perda de tag, FOV."""

import math

from app.sim.synthetic_vision import SyntheticVision


def test_tag_directly_ahead():
    """Tag diretamente à frente → z correto, x ≈ 0."""
    sv = SyntheticVision(seed=42)
    vs = sv.compute(
        robot_x=100,
        robot_y=100,
        robot_theta=0,
        tag_x=130,
        tag_y=100,
        tag_theta=math.pi,
        tag_id=5,
    )
    assert vs.detectado
    assert vs.id == 5
    assert vs.z_cm is not None
    assert abs(vs.z_cm - 30.0) < 2.0
    assert abs(vs.x_cm) < 2.0


def test_tag_to_the_right():
    """Tag à direita → x positivo."""
    sv = SyntheticVision(seed=42)
    vs = sv.compute(
        robot_x=100,
        robot_y=100,
        robot_theta=0,
        tag_x=120,
        tag_y=110,
        tag_theta=math.pi,
    )
    assert vs.detectado
    assert vs.x_cm is not None
    assert vs.x_cm > 0


def test_tag_out_of_fov():
    """Tag atrás do robô → não detectada."""
    sv = SyntheticVision(seed=42)
    vs = sv.compute(
        robot_x=100,
        robot_y=100,
        robot_theta=0,
        tag_x=50,
        tag_y=100,
        tag_theta=0,
    )
    assert not vs.detectado


def test_tag_too_far():
    """Tag além do alcance máximo → não detectada."""
    sv = SyntheticVision(seed=42)
    vs = sv.compute(
        robot_x=0,
        robot_y=100,
        robot_theta=0,
        tag_x=300,
        tag_y=100,
        tag_theta=math.pi,
    )
    assert not vs.detectado


def test_tag_too_close():
    """Tag abaixo do alcance mínimo → não detectada."""
    sv = SyntheticVision(seed=42)
    vs = sv.compute(
        robot_x=100,
        robot_y=100,
        robot_theta=0,
        tag_x=101,
        tag_y=100,
        tag_theta=math.pi,
    )
    assert not vs.detectado


def test_tag_hidden():
    """Tag oculta (injeção de falha) → não detectada."""
    sv = SyntheticVision(seed=42)
    sv.set_tag_hidden(True)
    vs = sv.compute(
        robot_x=100,
        robot_y=100,
        robot_theta=0,
        tag_x=130,
        tag_y=100,
        tag_theta=math.pi,
    )
    assert not vs.detectado

    sv.set_tag_hidden(False)
    vs = sv.compute(
        robot_x=100,
        robot_y=100,
        robot_theta=0,
        tag_x=130,
        tag_y=100,
        tag_theta=math.pi,
    )
    assert vs.detectado


def test_deterministic_with_seed():
    """Mesma seed → mesmos resultados."""
    results = []
    for _ in range(3):
        sv = SyntheticVision(seed=123)
        vs = sv.compute(
            robot_x=100,
            robot_y=100,
            robot_theta=0,
            tag_x=130,
            tag_y=100,
            tag_theta=math.pi,
        )
        results.append((vs.z_cm, vs.x_cm, vs.pitch_deg))

    assert results[0] == results[1] == results[2]
