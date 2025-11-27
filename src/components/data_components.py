from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from src.core.ecs import Component

@dataclass(slots=True)
class PositionComponent(Component):
    x: int
    y: int

@dataclass(slots=True)
class MovementComponent(Component):
    path: List[Tuple[int, int]] = field(default_factory=list)
    speed: float = 1.0
    target: Optional[Tuple[int, int]] = None
    progress: float = 0.0  # Progress to next tile (0.0 to 1.0)

@dataclass(slots=True)
class ResourceComponent(Component):
    resource_type: str  # e.g., "tree_oak"
    health: int
    max_health: int
    drops: dict = field(default_factory=dict)  # {"log": [min, max], "sapling": [min, max]}

@dataclass(slots=True)
class ActionComponent(Component):
    current_action: str = "idle"  # "idle", "move", "chop"
    target_entity_id: Optional[int] = None
    target_pos: Optional[Tuple[int, int]] = None

