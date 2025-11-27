from dataclasses import dataclass, field
from typing import Dict
from src.core.ecs import Component

@dataclass(slots=True)
class SkillComponent(Component):
    # Dictionary of skill name to proficiency level (0.0 to 1.0)
    # e.g., {"logging": 0.1, "farming": 0.5}
    skills: Dict[str, float] = field(default_factory=dict)

