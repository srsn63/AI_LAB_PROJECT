from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional
import random


class TerrainType(Enum):
    FLOOR = "floor"
    WATER = "water"
    WALL = "wall"


@dataclass(frozen=True)
class Tile:
    terrain: TerrainType
    cost: float


TERRAIN_WEIGHTS = {
    TerrainType.FLOOR: 0.6,
    TerrainType.WATER: 0.25,
    TerrainType.WALL: 0.15,
}

TERRAIN_COSTS = {
    TerrainType.FLOOR: 1.0,
    TerrainType.WATER: 3.0,
    TerrainType.WALL: 5.0,
}


@dataclass
class World:
    width: int
    height: int
    grid: List[List[Tile]] = field(default_factory=list)

    def generate(self, seed: Optional[int] = None) -> None:
        rng = random.Random(seed)
        terrain_types = list(TERRAIN_WEIGHTS.keys())
        weights = list(TERRAIN_WEIGHTS.values())

        self.grid = []
        for _y in range(self.height):
            row: List[Tile] = []
            for _x in range(self.width):
                terrain = rng.choices(terrain_types, weights=weights, k=1)[0]
                cost = TERRAIN_COSTS[terrain]
                row.append(Tile(terrain=terrain, cost=cost))
            self.grid.append(row)

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
