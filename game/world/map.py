from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional
import random


class TerrainType(Enum):
    FLOOR = "floor"
    WATER = "water"
    WALL = "wall"
    MUD = "mud"
    GRASS = "grass"
    ROCK = "rock"


@dataclass(frozen=True)
class Tile:
    terrain: TerrainType
    cost: float


TERRAIN_COSTS = {
    TerrainType.FLOOR: 1.0,
    TerrainType.WATER: 5.0,
    TerrainType.WALL: 99.0, # Essentially impassable for A*
    TerrainType.MUD: 3.0,
    TerrainType.GRASS: 1.2,
    TerrainType.ROCK: 2.0,
}


@dataclass
class ResourceEntity:
    x: int
    y: int
    type: str # "scrap", "food", "ammo"
    amount: int

@dataclass
class World:
    width: int
    height: int
    grid: List[List[Tile]] = field(default_factory=list)
    resources: List[ResourceEntity] = field(default_factory=list)

    def generate(self, seed: Optional[int] = None) -> None:
        from game.world.generator import MapGenerator
        generator = MapGenerator(self.width, self.height, seed=seed)
        self.grid, self.resources = generator.generate()

    def get_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        neighbors: List[Tuple[int, int]] = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx = x + dx
            ny = y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                neighbors.append((nx, ny))
        return neighbors

    def get_cost(self, x: int, y: int) -> float:
        return self.grid[y][x].cost

    def get_resource_at(self, x: int, y: int) -> Optional[ResourceEntity]:
        for res in self.resources:
            if res.x == x and res.y == y:
                return res
        return None

    def is_walkable(self, x: int, y: int) -> bool:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x].terrain != TerrainType.WALL
        return False
