from dataclasses import dataclass
from src.core.ecs import Component

@dataclass(slots=True)
class IsWalkable(Component):
    pass

@dataclass(slots=True)
class IsTree(Component):
    pass

@dataclass(slots=True)
class IsSelectable(Component):
    pass

@dataclass(slots=True)
class IsPlayer(Component):
    pass

@dataclass(slots=True)
class IsVillager(Component):
    pass

