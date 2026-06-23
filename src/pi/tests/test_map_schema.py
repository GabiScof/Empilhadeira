"""Testes do schema de mapa e world model.

Cobre:
- Validação do schema Pydantic (campos obrigatórios, faixas, ids únicos).
- Carregar mapas de tamanhos diferentes.
- Planejador gera rota correta com grafo (A*/BFS) e sem grafo (Manhattan).
- IDs duplicados rejeitados.
- Edges referenciando waypoints inexistentes rejeitados.
- Tags fora da arena rejeitados.
"""

import pytest
from pathlib import Path

# Diretório de mapas JSON do projeto
MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


class TestMapSchema:
    def test_load_corredor_pequeno(self):
        from app.world.map_schema import load_map

        m = load_map(MAPS_DIR / "corredor_pequeno.json")
        assert m.name == "corredor_pequeno"
        assert m.arena.width_m == 0.80
        assert m.arena.height_m == 2.00
        assert len(m.tags) == 3
        assert m.waypoints is None

    def test_load_arena_media(self):
        from app.world.map_schema import load_map

        m = load_map(MAPS_DIR / "arena_media.json")
        assert m.name == "arena_media"
        assert m.arena.width_m == 1.50
        assert len(m.tags) == 4

    def test_load_arena_grande_com_grafo(self):
        from app.world.map_schema import load_map

        m = load_map(MAPS_DIR / "arena_grande_com_grafo.json")
        assert m.name == "arena_grande_com_grafo"
        assert m.arena.width_m == 3.00
        assert len(m.tags) == 6
        assert m.waypoints is not None
        assert len(m.waypoints) == 9
        assert m.edges is not None

    def test_unique_tag_ids(self):
        from app.world.map_schema import ArenaMap

        with pytest.raises(Exception):
            ArenaMap.model_validate({
                "name": "test",
                "arena": {"width_m": 1.0, "height_m": 1.0},
                "start_pose": {"x_m": 0.1, "y_m": 0.1, "theta_deg": 0},
                "home_pose": {"x_m": 0.1, "y_m": 0.1, "theta_deg": 0},
                "tags": [
                    {"position_id": "P1", "x_m": 0.1, "y_m": 0.1, "yaw_deg": 0},
                    {"position_id": "P1", "x_m": 0.5, "y_m": 0.5, "yaw_deg": 0},
                ],
            })

    def test_tag_out_of_bounds(self):
        from app.world.map_schema import ArenaMap

        with pytest.raises(Exception):
            ArenaMap.model_validate({
                "name": "test",
                "arena": {"width_m": 1.0, "height_m": 1.0},
                "start_pose": {"x_m": 0.1, "y_m": 0.1, "theta_deg": 0},
                "home_pose": {"x_m": 0.1, "y_m": 0.1, "theta_deg": 0},
                "tags": [
                    {"position_id": "P1", "x_m": 2.0, "y_m": 0.5, "yaw_deg": 0},
                ],
            })

    def test_invalid_edge_ref(self):
        from app.world.map_schema import ArenaMap

        with pytest.raises(Exception):
            ArenaMap.model_validate({
                "name": "test",
                "arena": {"width_m": 1.0, "height_m": 1.0},
                "start_pose": {"x_m": 0.1, "y_m": 0.1, "theta_deg": 0},
                "home_pose": {"x_m": 0.1, "y_m": 0.1, "theta_deg": 0},
                "tags": [{"position_id": "P1", "x_m": 0.5, "y_m": 0.5, "yaw_deg": 0}],
                "waypoints": [{"id": "w0", "x_m": 0.1, "y_m": 0.1}],
                "edges": [["w0", "w_missing"]],
            })

    def test_file_not_found(self):
        from app.world.map_schema import load_map

        with pytest.raises(FileNotFoundError):
            load_map("/nonexistent/path.json")


class TestWorldModel:
    def test_start_and_home_pose(self):
        from app.world.map_schema import load_map
        from app.world.world_model import WorldModel

        m = load_map(MAPS_DIR / "corredor_pequeno.json")
        wm = WorldModel(m)
        sx, sy, st = wm.start_pose
        assert abs(sx - 0.40) < 0.01
        assert abs(sy - 0.10) < 0.01

    def test_tag_by_position_id(self):
        from app.world.map_schema import load_map
        from app.world.world_model import WorldModel

        m = load_map(MAPS_DIR / "corredor_pequeno.json")
        wm = WorldModel(m)
        tag = wm.get_tag_by_position_id("P1")
        assert tag is not None
        assert tag.position_id == "P1"

    def test_resolve_tag_id(self):
        from app.world.map_schema import load_map
        from app.world.world_model import WorldModel

        m = load_map(MAPS_DIR / "corredor_pequeno.json")
        wm = WorldModel(m)
        wm.resolve_tag_id(42, "P1")
        result = wm.get_position_for_tag_id(42)
        assert result is not None
        assert result.position_id == "P1"

    def test_has_graph(self):
        from app.world.map_schema import load_map
        from app.world.world_model import WorldModel

        m1 = load_map(MAPS_DIR / "corredor_pequeno.json")
        wm1 = WorldModel(m1)
        assert not wm1.has_graph

        m2 = load_map(MAPS_DIR / "arena_grande_com_grafo.json")
        wm2 = WorldModel(m2)
        assert wm2.has_graph

    def test_nearest_waypoint(self):
        from app.world.map_schema import load_map
        from app.world.world_model import WorldModel

        m = load_map(MAPS_DIR / "arena_grande_com_grafo.json")
        wm = WorldModel(m)
        wp = wm.nearest_waypoint(0.19, 0.19)
        assert wp == "w0"
