import time
from dataclasses import dataclass, field
from typing import Any, Type, TypeVar, Optional, Dict, Set, List, Iterable, Tuple

# --- Component ---
@dataclass(slots=True)
class Component:
    """Base class for all components. Subclasses should be dataclasses."""
    pass

T = TypeVar('T', bound=Component)

# --- System ---
class System:
    """Base class for all systems."""
    def update(self, dt: float):
        raise NotImplementedError

# --- EntityManager ---
class EntityManager:
    def __init__(self):
        self._next_entity_id: int = 0
        self._entities: Set[int] = set()
        # component_type -> {entity_id -> component_instance}
        self._components: Dict[Type[Component], Dict[int, Component]] = {}
        
        # Cache for queries could be added here, but keeping it simple for now.

    def create_entity(self) -> int:
        """Creates a new entity ID."""
        entity = self._next_entity_id
        self._next_entity_id += 1
        self._entities.add(entity)
        return entity

    def destroy_entity(self, entity: int):
        """Removes an entity and all its components."""
        if entity in self._entities:
            self._entities.remove(entity)
            for store in self._components.values():
                if entity in store:
                    del store[entity]

    def has_entity(self, entity: int) -> bool:
        """Checks if an entity exists."""
        return entity in self._entities

    def add_component(self, entity: int, component: Component):
        """Adds a component to an entity."""
        comp_type = type(component)
        if comp_type not in self._components:
            self._components[comp_type] = {}
        self._components[comp_type][entity] = component

    def remove_component(self, entity: int, comp_type: Type[T]):
        """Removes a component from an entity."""
        if comp_type in self._components and entity in self._components[comp_type]:
            del self._components[comp_type][entity]

    def get_component(self, entity: int, comp_type: Type[T]) -> Optional[T]:
        """Retrieves a specific component for an entity."""
        if comp_type in self._components:
            return self._components[comp_type].get(entity)
        return None

    def has_component(self, entity: int, comp_type: Type[Component]) -> bool:
        """Checks if an entity has a specific component."""
        return comp_type in self._components and entity in self._components[comp_type]

    def get_entities_with(self, *comp_types: Type[Component]) -> Iterable[Tuple[int, ...]]:
        """
        Yields (entity_id, comp1, comp2, ...) for entities that have ALL specified components.
        This is a basic implementation. For production, consider Archetypes or Bitmasks.
        """
        if not comp_types:
            return

        # Find the component type with the fewest entities to iterate over
        # to minimize checks.
        sorted_types = sorted(comp_types, key=lambda t: len(self._components.get(t, {})))
        primary_type = sorted_types[0]
        other_types = sorted_types[1:]

        primary_store = self._components.get(primary_type, {})
        
        # Create a copy to allow modification during iteration
        for entity, primary_comp in list(primary_store.items()):
            components = [primary_comp]
            has_all = True
            for ot in other_types:
                store = self._components.get(ot)
                if store is None or entity not in store:
                    has_all = False
                    break
                components.append(store[entity])
            
            if has_all:
                # We need to return components in the order requested, not sorted order
                # Re-fetch based on original order is safest/clearest
                yield tuple([entity] + [self._components[t][entity] for t in comp_types])
