"""Modelo de mundo paramétrico — arena, tags e robô carregados de arquivo.

[ref: Seção 2 do mega-prompt]
"""

from app.world.map_schema import ArenaMap
from app.world.robot_model import RobotModel
from app.world.world_model import WorldModel

__all__ = ["ArenaMap", "RobotModel", "WorldModel"]
