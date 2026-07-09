"""Planejador de rotas genérico — funciona em qualquer mapa.

Estratégias:
1. **Grafo (A*/BFS):** quando o mapa tem waypoints/edges, roteia por A* sobre
   as arestas e gera segmentos entre waypoints consecutivos.
2. **Manhattan (arena aberta):** sem grafo, alinha um eixo e depois o outro.
   Gera segmentos FORWARD/TURN em sequência alinhada à grade.

Saída: lista de Segment (FORWARD com distância ou TURN com ângulo livre).
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.world.world_model import WorldModel


class SegmentType(StrEnum):
    FORWARD = "FORWARD"
    TURN = "TURN"


@dataclass
class Segment:
    """Um segmento da rota: avançar ou girar.

    Atributos:
        type: FORWARD ou TURN.
        value: distância (m) para FORWARD, ângulo (rad) para TURN.
        target_x: posição X do destino do segmento (m) — para FORWARD.
        target_y: posição Y do destino do segmento (m) — para FORWARD.
        target_heading: heading alvo após o segmento (rad).
    """

    type: SegmentType
    value: float
    target_x: float = 0.0
    target_y: float = 0.0
    target_heading: float = 0.0

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "value": round(self.value, 4),
            "target_x": round(self.target_x, 4),
            "target_y": round(self.target_y, 4),
            "target_heading": round(self.target_heading, 4),
        }


def _normalize_angle(a: float) -> float:
    """Normaliza ângulo para [-π, π]."""
    return math.atan2(math.sin(a), math.cos(a))


def _heading_between(x1: float, y1: float, x2: float, y2: float) -> float:
    """Heading de (x1,y1) para (x2,y2)."""
    return math.atan2(y2 - y1, x2 - x1)


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _waypoints_to_segments(
    start_x: float,
    start_y: float,
    start_heading: float,
    waypoint_coords: list[tuple[float, float]],
    final_heading: float | None = None,
) -> list[Segment]:
    """Converte sequência de waypoints em segmentos FORWARD/TURN.

    Para cada par consecutivo de waypoints: calcula o heading necessário, gira
    para esse heading, avança a distância.
    """
    segments: list[Segment] = []
    cx, cy, ch = start_x, start_y, start_heading

    for wx, wy in waypoint_coords:
        dist = _distance(cx, cy, wx, wy)
        if dist < 0.005:
            continue

        needed_heading = _heading_between(cx, cy, wx, wy)
        turn = _normalize_angle(needed_heading - ch)

        if abs(turn) > 0.02:  # ~1°
            segments.append(Segment(
                type=SegmentType.TURN,
                value=turn,
                target_x=cx,
                target_y=cy,
                target_heading=needed_heading,
            ))

        segments.append(Segment(
            type=SegmentType.FORWARD,
            value=dist,
            target_x=wx,
            target_y=wy,
            target_heading=needed_heading,
        ))

        cx, cy, ch = wx, wy, needed_heading

    if final_heading is not None:
        final_turn = _normalize_angle(final_heading - ch)
        if abs(final_turn) > 0.02:
            segments.append(Segment(
                type=SegmentType.TURN,
                value=final_turn,
                target_x=cx,
                target_y=cy,
                target_heading=final_heading,
            ))

    return segments


def _astar(
    graph: dict[str, list[str]],
    start: str,
    goal: str,
    world: "WorldModel",
) -> list[str] | None:
    """A* sobre o grafo de waypoints.

    Returns:
        Lista de IDs de waypoints do start ao goal, ou None se não há caminho.
    """
    start_xy = world.waypoint_xy(start)
    goal_xy = world.waypoint_xy(goal)
    if start_xy is None or goal_xy is None:
        return None

    def heuristic(wp_id: str) -> float:
        xy = world.waypoint_xy(wp_id)
        if xy is None:
            return float("inf")
        return _distance(xy[0], xy[1], goal_xy[0], goal_xy[1])

    open_set: list[tuple[float, str]] = [(heuristic(start), start)]
    came_from: dict[str, str] = {}
    g_score: dict[str, float] = {start: 0.0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return list(reversed(path))

        current_xy = world.waypoint_xy(current)
        if current_xy is None:
            continue

        for neighbor in graph.get(current, []):
            neighbor_xy = world.waypoint_xy(neighbor)
            if neighbor_xy is None:
                continue
            tentative_g = g_score[current] + _distance(
                current_xy[0], current_xy[1], neighbor_xy[0], neighbor_xy[1]
            )
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic(neighbor)
                heapq.heappush(open_set, (f, neighbor))

    return None


def _plan_with_graph(
    start_x: float,
    start_y: float,
    start_heading: float,
    goal_x: float,
    goal_y: float,
    goal_heading: float | None,
    world: "WorldModel",
) -> list[Segment] | None:
    """Planeja rota usando o grafo de waypoints do mapa."""
    graph = world.graph
    if graph is None:
        return None

    start_wp = world.nearest_waypoint(start_x, start_y)
    goal_wp = world.nearest_waypoint(goal_x, goal_y)
    if start_wp is None or goal_wp is None:
        return None

    if start_wp == goal_wp:
        waypoint_coords = []
        wp_xy = world.waypoint_xy(start_wp)
        if wp_xy:
            waypoint_coords.append(wp_xy)
        waypoint_coords.append((goal_x, goal_y))
        return _waypoints_to_segments(
            start_x, start_y, start_heading, waypoint_coords, goal_heading
        )

    path = _astar(graph, start_wp, goal_wp, world)
    if path is None:
        return None

    waypoint_coords: list[tuple[float, float]] = []
    for wp_id in path:
        xy = world.waypoint_xy(wp_id)
        if xy:
            waypoint_coords.append(xy)

    waypoint_coords.append((goal_x, goal_y))

    return _waypoints_to_segments(
        start_x, start_y, start_heading, waypoint_coords, goal_heading
    )


def _plan_manhattan(
    start_x: float,
    start_y: float,
    start_heading: float,
    goal_x: float,
    goal_y: float,
    goal_heading: float | None,
) -> list[Segment]:
    """Planeja rota Manhattan: primeiro alinha X, depois Y."""
    mid_x, mid_y = goal_x, start_y

    waypoint_coords: list[tuple[float, float]] = []

    if _distance(start_x, start_y, mid_x, mid_y) > 0.01:
        waypoint_coords.append((mid_x, mid_y))

    if _distance(mid_x, mid_y, goal_x, goal_y) > 0.01:
        waypoint_coords.append((goal_x, goal_y))

    if not waypoint_coords:
        if goal_heading is not None:
            turn = _normalize_angle(goal_heading - start_heading)
            if abs(turn) > 0.02:
                return [Segment(
                    type=SegmentType.TURN,
                    value=turn,
                    target_x=start_x,
                    target_y=start_y,
                    target_heading=goal_heading,
                )]
        return []

    return _waypoints_to_segments(
        start_x, start_y, start_heading, waypoint_coords, goal_heading
    )


def plan_route(
    start_x: float,
    start_y: float,
    start_heading: float,
    goal_x: float,
    goal_y: float,
    goal_heading: float | None,
    world: "WorldModel | None" = None,
) -> list[Segment]:
    """Planeja rota de pose atual até pose alvo.

    Escolhe automaticamente entre planejamento por grafo (A*) e Manhattan
    conforme o mapa.

    Args:
        start_x, start_y: posição atual (m).
        start_heading: heading atual (rad).
        goal_x, goal_y: destino (m).
        goal_heading: heading final desejado (rad), ou None para qualquer.
        world: modelo do mundo (para acessar o grafo).

    Returns:
        Lista de Segment (FORWARD/TURN).
    """
    if world is not None and world.has_graph:
        result = _plan_with_graph(
            start_x, start_y, start_heading,
            goal_x, goal_y, goal_heading,
            world,
        )
        if result is not None:
            return result

    return _plan_manhattan(
        start_x, start_y, start_heading,
        goal_x, goal_y, goal_heading,
    )
