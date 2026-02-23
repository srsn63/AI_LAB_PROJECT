from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class BaseAgent:
    """Server-side agent data container. AI logic lives on the client."""
    id: int
    x: int
    y: int
    health: float = 100.0
    max_health: float = 100.0
    ammo: int = 0
    inventory: Dict[str, int] = field(default_factory=dict)
    upgrades: Dict[Any, int] = field(default_factory=dict)
