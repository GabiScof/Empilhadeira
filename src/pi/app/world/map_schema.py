"""Schema Pydantic do arquivo de mapa da arena.

Um mapa descreve completamente uma arena: dimensões, pose inicial do robô,
posição das AprilTags e, opcionalmente, um grafo de waypoints para arenas
com restrições (corredores, paredes internas).

Formato: JSON. Validação por Pydantic v2.
"""

from __future__ import annotations

import math
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class ArenaSpec(BaseModel):
    """Dimensões da arena retangular."""
    width_m: float = Field(gt=0, description="Largura da arena (m).")
    height_m: float = Field(gt=0, description="Altura/comprimento da arena (m).")
    origin: str = Field("bottom_left", description="Referência do sistema de coordenadas.")


class PoseSpec(BaseModel):
    """Pose 2D: posição + orientação."""
    x_m: float = Field(description="Posição X (m).")
    y_m: float = Field(description="Posição Y (m).")
    theta_deg: float = Field(description="Orientação (graus, sentido anti-horário a partir de +X).")

    @property
    def theta_rad(self) -> float:
        return math.radians(self.theta_deg)


class TagSpec(BaseModel):
    """Posição conhecida de uma AprilTag na arena."""
    position_id: str = Field(description="Identificador da posição (ex: P1, P2).")
    x_m: float = Field(description="Posição X da tag (m).")
    y_m: float = Field(description="Posição Y da tag (m).")
    wall: str | None = Field(None, description="Parede onde a tag está (left/right/top/bottom).")
    yaw_deg: float = Field(description="Orientação da tag (graus).")
    april_tag_id: int | None = Field(
        None,
        ge=0,
        description="ID numérico impresso na tag física (tag25h9: 0–34). "
        "Obrigatório para o robô real resolver qual tag do mapa foi vista.",
    )

    @property
    def yaw_rad(self) -> float:
        return math.radians(self.yaw_deg)


class WaypointSpec(BaseModel):
    """Ponto navegável do grafo opcional."""
    id: str = Field(description="Identificador único do waypoint.")
    x_m: float = Field(description="Posição X (m).")
    y_m: float = Field(description="Posição Y (m).")


class ArenaMap(BaseModel):
    """Schema completo de um arquivo de mapa.

    Valida campos obrigatórios, unicidade de IDs e referências de arestas.
    """
    name: str = Field(description="Nome descritivo do mapa.")
    arena: ArenaSpec
    start_pose: PoseSpec
    home_pose: PoseSpec
    tags: list[TagSpec] = Field(min_length=1)
    waypoints: list[WaypointSpec] | None = None
    edges: list[list[str]] | None = None
    tag_size_m: float = Field(
        0.04,
        gt=0,
        description="Tamanho físico da AprilTag (m). Tag real medida: 4 cm "
        "(= APRILTAG_SIZE_CM; manter consistente).",
    )
    tag_family: str = Field("tag25h9", description="Família de tags.")

    @model_validator(mode="after")
    def _validate_map(self) -> "ArenaMap":
        tag_ids = [t.position_id for t in self.tags]
        if len(tag_ids) != len(set(tag_ids)):
            raise ValueError("position_id das tags deve ser único")

        assigned_ids = [t.april_tag_id for t in self.tags if t.april_tag_id is not None]
        if len(assigned_ids) != len(set(assigned_ids)):
            raise ValueError("april_tag_id das tags deve ser único")

        for tag in self.tags:
            if not (0 <= tag.x_m <= self.arena.width_m):
                raise ValueError(
                    f"Tag {tag.position_id}: x_m={tag.x_m} fora da arena "
                    f"[0, {self.arena.width_m}]"
                )
            if not (0 <= tag.y_m <= self.arena.height_m):
                raise ValueError(
                    f"Tag {tag.position_id}: y_m={tag.y_m} fora da arena "
                    f"[0, {self.arena.height_m}]"
                )

        if self.waypoints:
            wp_ids = [w.id for w in self.waypoints]
            if len(wp_ids) != len(set(wp_ids)):
                raise ValueError("id dos waypoints deve ser único")

            if self.edges:
                wp_set = set(wp_ids)
                for edge in self.edges:
                    if len(edge) != 2:
                        raise ValueError(f"Aresta deve ter exatamente 2 nós: {edge}")
                    for node in edge:
                        if node not in wp_set:
                            raise ValueError(f"Aresta referencia waypoint inexistente: {node}")

        return self


def load_map(path: str | Path) -> ArenaMap:
    """Carrega e valida um arquivo de mapa JSON.

    Args:
        path: caminho para o arquivo .json.

    Returns:
        ArenaMap validado.

    Raises:
        FileNotFoundError: se o arquivo não existe.
        pydantic.ValidationError: se o JSON não bate com o schema.
    """
    import json

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Mapa não encontrado: {p}")

    with open(p) as f:
        data = json.load(f)

    return ArenaMap.model_validate(data)
