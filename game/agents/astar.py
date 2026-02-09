from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappush, heappop
from typing import Dict, List, Optional, Protocol, Tuple


class PathfindingMap(Protocol):
    def get_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        ...

    def get_cost(self, x: int, y: int) -> float:
        ...


Coord = Tuple[int, int]


def manhattan(a: Coord, b: Coord) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass(order=True)
class _Node:
    priority: float
    position: Coord = field(compare=False)


class AStar:
    def find_path(
        self,
        start: Coord,
        goal: Coord,
        nav_map: PathfindingMap,
    ) -> List[Coord]:
        if start == goal:
            return [start]

        open_set: List[_Node] = []
        heappush(open_set, _Node(priority=0.0, position=start))

        came_from: Dict[Coord, Coord] = {}
        g_score: Dict[Coord, float] = {start: 0.0}

        while open_set:
            current_node = heappop(open_set)
            current = current_node.position

            if current == goal:
                return self._reconstruct_path(came_from, current)

            for neighbor in nav_map.get_neighbors(*current):
                tentative_g = g_score[current] + nav_map.get_cost(*neighbor)
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + manhattan(neighbor, goal)
                    heappush(open_set, _Node(priority=f_score, position=neighbor))

        return []

    def _reconstruct_path(
        self,
        came_from: Dict[Coord, Coord],
        current: Coord,
    ) -> List[Coord]:
        path: List[Coord] = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path
