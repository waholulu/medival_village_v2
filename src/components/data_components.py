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
    current_action: str = "idle"  # "idle", "move", "chop", "pickup", "drop"
    target_entity_id: Optional[int] = None
    target_pos: Optional[Tuple[int, int]] = None

@dataclass(slots=True)
class InventoryComponent(Component):
    items: dict = field(default_factory=dict)  # {"log": 5}
    capacity: int = 10

@dataclass(slots=True)
class ItemComponent(Component):
    item_type: str # "log"
    amount: int = 1
    food_value: float = 0.0  # Amount of hunger reduction when consumed (0 = not food)

@dataclass(slots=True)
class JobComponent(Component):
    job_id: str
    job_type: str
    target_pos: Optional[Tuple[int, int]] = None
    target_entity_id: Optional[int] = None

@dataclass(slots=True)
class HungerComponent(Component):
    hunger: float = 0.0  # 0-100, increases over time, decreases when eating

@dataclass(slots=True)
class TirednessComponent(Component):
    tiredness: float = 0.0  # 0-100, increases when working, decreases when sleeping

@dataclass(slots=True)
class MoodComponent(Component):
    mood: float = 50.0  # 0-100, affects work efficiency, influenced by food/rest/social

@dataclass(slots=True)
class DurabilityComponent(Component):
    current: float
    max: float

@dataclass(slots=True)
class CropComponent(Component):
    crop_type: str  # e.g., "wheat"
    growth_progress: float = 0.0  # 0.0 to 1.0
    state: str = "seed"  # "seed", "growing", "ripe"
    planted_time: float = 0.0  # Game time when planted

@dataclass(slots=True)
class SleepStateComponent(Component):
    is_sleeping: bool = False
    sleep_location: Optional[Tuple[int, int]] = None

@dataclass(slots=True)
class RoutineComponent(Component):
    current_state: str = "WORKING"  # "SLEEPING", "WAKING", "EATING", "WORKING", "SOCIALIZING"
    next_scheduled_activity: Optional[str] = None

