from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any

from game.agents.astar import AStar, Coord, PathfindingMap
from game.agents.fsm import FiniteStateMachine
from game.agents.minimax import Minimax


@dataclass
class BaseAgent:
    id: int
    x: int
    y: int
    health: float = 100.0
    ammo: int = 0
    inventory: Dict[str, int] = field(default_factory=dict)
    
    path: List[Coord] = field(default_factory=list)
    _path_index: int = 0
    _navigator: AStar = field(default_factory=AStar, repr=False)
    
    # FSM Controller
    fsm: FiniteStateMachine = field(init=False, repr=False)
    minimax: Optional[Minimax] = field(default=None, repr=False)

    def __post_init__(self):
        self.fsm = FiniteStateMachine(self, minimax=self.minimax)
        # Set initial state
        self.fsm.set_state("SCAVENGE")

    def set_navigator(self, navigator: AStar):
        """Pluggable navigator."""
        self._navigator = navigator

    def set_path(self, path: List[Coord]) -> None:
        self.path = path
        self._path_index = 0

    def plan_path(
        self,
        target: Coord,
        nav_map: PathfindingMap,
    ) -> None:
        start = (self.x, self.y)
        path = self._navigator.find_path(start, target, nav_map)
        self.set_path(path)

    def update(self, world_state) -> None:
        # Update FSM logic first
        self.fsm.update(world_state)
        
        # Then execute movement if path exists
        if self.path and self._path_index < len(self.path):
            next_pos = self.path[self._path_index]
            self.x, self.y = next_pos
            self._path_index += 1
