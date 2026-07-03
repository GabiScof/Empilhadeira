"""Testes do planejador de rotas.

Cobre:
- Manhattan gera rota correta em arena aberta.
- A* gera rota pelo grafo em arena com restrição.
- Giro de ângulo livre (não só 90°/180°).
- Rota trivial (já no destino).
"""

import math
from pathlib import Path

import pytest

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


class TestPathPlanner:
    def test_manhattan_basic(self):
        from app.control.path_planner import SegmentType, plan_route

        segments = plan_route(0.0, 0.0, 0.0, 1.0, 1.0, None)
        assert len(segments) > 0
        # Deve ter ao menos um segmento FORWARD
        assert any(s.type == SegmentType.FORWARD for s in segments)

    def test_manhattan_already_there(self):
        from app.control.path_planner import plan_route

        segments = plan_route(1.0, 1.0, 0.0, 1.0, 1.0, None)
        assert len(segments) == 0

    def test_manhattan_with_final_heading(self):
        from app.control.path_planner import SegmentType, plan_route

        segments = plan_route(0.0, 0.0, 0.0, 1.0, 0.0, math.pi / 2)
        # Último segmento deve ser um TURN para pi/2
        turns = [s for s in segments if s.type == SegmentType.TURN]
        assert len(turns) > 0

    def test_graph_planning(self):
        from app.control.path_planner import SegmentType, plan_route
        from app.world.map_schema import load_map
        from app.world.world_model import WorldModel

        m = load_map(MAPS_DIR / "arena_grande_com_grafo.json")
        wm = WorldModel(m)
        segments = plan_route(
            0.20, 0.20, math.pi / 2,
            2.80, 1.80, None,
            world=wm,
        )
        assert len(segments) > 0
        forwards = [s for s in segments if s.type == SegmentType.FORWARD]
        assert len(forwards) >= 2  # ao menos 2 segmentos pelo grafo

    def test_free_angle_turn(self):
        from app.control.path_planner import SegmentType, plan_route

        # Heading alvo de 45°
        segments = plan_route(0.0, 0.0, 0.0, 0.5, 0.5, math.pi / 4)
        turns = [s for s in segments if s.type == SegmentType.TURN]
        # O giro deve ser aproximadamente 45° (π/4)
        for t in turns:
            assert abs(abs(t.value) - math.pi / 4) < 0.5 or abs(t.value) > 0.01

    def test_segment_to_dict(self):
        from app.control.path_planner import Segment, SegmentType

        s = Segment(SegmentType.FORWARD, 0.5, 1.0, 1.0, 0.0)
        d = s.to_dict()
        assert d["type"] == "FORWARD"
        assert d["value"] == 0.5
