from dataclasses import dataclass, field
from typing import Dict
from src.core.ecs import Component

@dataclass(slots=True)
class BlueprintComponent(Component):
    building_type: str
    required_materials: Dict[str, int]
    current_materials: Dict[str, int] = field(default_factory=dict)
    work_required: float = 100.0
    work_completed: float = 0.0

@dataclass(slots=True)
class BuildingComponent(Component):
    building_type: str
