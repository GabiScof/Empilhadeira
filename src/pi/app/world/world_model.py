"""Modelo de mundo: carrega mapa, expõe arena, tags, start/home e grafo.

Interface principal entre o mapa JSON carregado e os módulos de navegação,
visão e simulação. Toda a geometria fica em SI (m, rad).

[ref: Seção 2 do mega-prompt]
"""

from __future__ import annotations

import math
from pathlib import Path

from app.world.map_schema import ArenaMap, TagSpec, load_map


class WorldModel:
    """Fachada sobre o mapa carregado.

    Expõe arena, tags, start/home, grafo de waypoints e métodos de consulta.
    """

    def __init__(self, arena_map: ArenaMap) -> None:
        self._map = arena_map
        self._tag_by_position: dict[str, TagSpec] = {
            t.position_id: t for t in arena_map.tags
        }
        self._tag_id_to_position: dict[int, str] = {}
        self._graph: dict[str, list[str]] | None = None

        if arena_map.waypoints and arena_map.edges:
            self._graph = {}
            for wp in arena_map.waypoints:
                self._graph[wp.id] = []
            for a, b in arena_map.edges:
                self._graph[a].append(b)
                self._graph[b].append(a)

    @classmethod
    def from_file(cls, path: str | Path) -> "WorldModel":
        """Carrega mundo a partir de arquivo JSON."""
        arena_map = load_map(path)
        return cls(arena_map)

    @property
    def map(self) -> ArenaMap:
        return self._map

    @property
    def arena_width_m(self) -> float:
        return self._map.arena.width_m

    @property
    def arena_height_m(self) -> float:
        return self._map.arena.height_m

    @property
    def start_pose(self) -> tuple[float, float, float]:
        """Pose inicial (x_m, y_m, theta_rad)."""
        sp = self._map.start_pose
        return sp.x_m, sp.y_m, sp.theta_rad

    @property
    def home_pose(self) -> tuple[float, float, float]:
        """Pose de casa (x_m, y_m, theta_rad)."""
        hp = self._map.home_pose
        return hp.x_m, hp.y_m, hp.theta_rad

    @property
    def tags(self) -> list[TagSpec]:
        return self._map.tags

    @property
    def tag_positions(self) -> dict[str, TagSpec]:
        """Mapa position_id → TagSpec."""
        return dict(self._tag_by_position)

    @property
    def has_graph(self) -> bool:
        return self._graph is not None

    @property
    def graph(self) -> dict[str, list[str]] | None:
        return self._graph

    def resolve_tag_id(self, april_tag_id: int, position_id: str) -> None:
        """Casa um ID de AprilTag lido pela câmera com uma posição do mapa.

        Args:
            april_tag_id: ID lido pela detecção.
            position_id: position_id mais próximo (por posição estimada).
        """
        self._tag_id_to_position[april_tag_id] = position_id

    def get_position_for_tag_id(self, april_tag_id: int) -> TagSpec | None:
        """Busca a posição conhecida pelo ID da tag já casado."""
        pid = self._tag_id_to_position.get(april_tag_id)
        if pid is None:
            return None
        return self._tag_by_position.get(pid)

    def get_tag_by_position_id(self, position_id: str) -> TagSpec | None:
        return self._tag_by_position.get(position_id)

    def tag_pose_m_rad(self, position_id: str) -> tuple[float, float, float] | None:
        """Retorna (x_m, y_m, yaw_rad) de uma tag pelo position_id."""
        tag = self._tag_by_position.get(position_id)
        if tag is None:
            return None
        return tag.x_m, tag.y_m, tag.yaw_rad

    def tag_approach_pose_m_rad(
        self, position_id: str, standoff_m: float = 0.15,
    ) -> tuple[float, float, float] | None:
        """Pose de aproximação PELA FRENTE da tag.

        O robô para a ``standoff_m`` metros na frente da face visível da tag,
        com heading apontando para ela (tag_yaw + π). Isso garante que a
        câmera veja o lado correto da tag — idêntico ao comportamento real.

        Returns:
            (x_m, y_m, heading_rad) da pose de approach, ou None.
        """
        tag = self._tag_by_position.get(position_id)
        if tag is None:
            return None
        approach_x = tag.x_m + standoff_m * math.cos(tag.yaw_rad)
        approach_y = tag.y_m + standoff_m * math.sin(tag.yaw_rad)
        facing_tag = tag.yaw_rad + math.pi
        facing_tag = math.atan2(math.sin(facing_tag), math.cos(facing_tag))
        return approach_x, approach_y, facing_tag

    def waypoint_xy(self, wp_id: str) -> tuple[float, float] | None:
        """Retorna (x_m, y_m) de um waypoint do grafo."""
        if not self._map.waypoints:
            return None
        for wp in self._map.waypoints:
            if wp.id == wp_id:
                return wp.x_m, wp.y_m
        return None

    def all_waypoint_ids(self) -> list[str]:
        if not self._map.waypoints:
            return []
        return [wp.id for wp in self._map.waypoints]

    def nearest_waypoint(self, x_m: float, y_m: float) -> str | None:
        """Encontra o waypoint mais próximo de (x, y)."""
        if not self._map.waypoints:
            return None
        best_id = None
        best_dist = float("inf")
        for wp in self._map.waypoints:
            d = math.hypot(wp.x_m - x_m, wp.y_m - y_m)
            if d < best_dist:
                best_dist = d
                best_id = wp.id
        return best_id

    def to_dict(self) -> dict:
        """Serializa para a API /sim/world-state."""
        result: dict = {
            "name": self._map.name,
            "arena": {
                "width_m": self.arena_width_m,
                "height_m": self.arena_height_m,
            },
            "start_pose": {
                "x_m": self._map.start_pose.x_m,
                "y_m": self._map.start_pose.y_m,
                "theta_deg": self._map.start_pose.theta_deg,
            },
            "home_pose": {
                "x_m": self._map.home_pose.x_m,
                "y_m": self._map.home_pose.y_m,
                "theta_deg": self._map.home_pose.theta_deg,
            },
            "tags": [
                {
                    "position_id": t.position_id,
                    "x_m": t.x_m,
                    "y_m": t.y_m,
                    "yaw_deg": t.yaw_deg,
                    "wall": t.wall,
                }
                for t in self._map.tags
            ],
            "tag_id_map": dict(self._tag_id_to_position),
            "has_graph": self.has_graph,
        }
        if self._map.waypoints:
            result["waypoints"] = [
                {"id": w.id, "x_m": w.x_m, "y_m": w.y_m}
                for w in self._map.waypoints
            ]
        if self._map.edges:
            result["edges"] = self._map.edges
        return result
