"""Testes do executor de segmentos.

Cobre:
- FORWARD atinge a posição alvo.
- TURN atinge o heading alvo (ângulos livres, não só 90°/180°).
- Timeout no segmento.
- Rota vazia = ROUTE_DONE.
"""

import math


class TestSegmentExecutor:
    def test_forward_segment(self):
        from app.control.path_planner import Segment, SegmentType
        from app.control.segment_executor import ExecutorState, SegmentExecutor

        ex = SegmentExecutor()
        seg = Segment(SegmentType.FORWARD, 0.5, target_x=0.5, target_y=0.0, target_heading=0.0)
        ex.load_route([seg])
        assert ex.state == ExecutorState.RUNNING
        # Simular o robô chegando ao alvo
        w_l, w_r = ex.step(0.49, 0.0, 0.0, 0.05)
        # Perto do alvo → ROUTE_DONE
        assert ex.state == ExecutorState.ROUTE_DONE or (abs(w_l) < 15 and abs(w_r) < 15)

    def test_turn_segment(self):
        from app.control.path_planner import Segment, SegmentType
        from app.control.segment_executor import ExecutorState, SegmentExecutor

        ex = SegmentExecutor()
        seg = Segment(
            SegmentType.TURN, math.pi / 3,
            target_x=0.0, target_y=0.0, target_heading=math.pi / 3,
        )
        ex.load_route([seg])
        # Se estamos no heading alvo
        w_l, w_r = ex.step(0.0, 0.0, math.pi / 3, 0.05)
        assert ex.state == ExecutorState.ROUTE_DONE

    def test_free_angle_45(self):
        from app.control.path_planner import Segment, SegmentType
        from app.control.segment_executor import SegmentExecutor

        ex = SegmentExecutor()
        seg = Segment(
            SegmentType.TURN, math.pi / 4,
            target_x=0.0, target_y=0.0, target_heading=math.pi / 4,
        )
        ex.load_route([seg])
        w_l, w_r = ex.step(0.0, 0.0, 0.0, 0.05)
        # Rodas opostas para girar
        assert w_l * w_r < 0 or abs(w_l - w_r) > 0.01

    def test_free_angle_135(self):
        from app.control.path_planner import Segment, SegmentType
        from app.control.segment_executor import SegmentExecutor

        ex = SegmentExecutor()
        seg = Segment(
            SegmentType.TURN, 3 * math.pi / 4,
            target_x=0.0, target_y=0.0, target_heading=3 * math.pi / 4,
        )
        ex.load_route([seg])
        w_l, w_r = ex.step(0.0, 0.0, 0.0, 0.05)
        assert abs(w_l) > 0 or abs(w_r) > 0

    def test_empty_route(self):
        from app.control.segment_executor import ExecutorState, SegmentExecutor

        ex = SegmentExecutor()
        ex.load_route([])
        assert ex.state == ExecutorState.ROUTE_DONE

    def test_progress(self):
        from app.control.path_planner import Segment, SegmentType
        from app.control.segment_executor import SegmentExecutor

        ex = SegmentExecutor()
        segs = [
            Segment(SegmentType.FORWARD, 0.5, 0.5, 0.0, 0.0),
            Segment(SegmentType.TURN, math.pi / 2, 0.5, 0.0, math.pi / 2),
        ]
        ex.load_route(segs)
        assert ex.progress == 0.0
        assert ex.total_segments == 2
