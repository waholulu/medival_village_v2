from typing import Optional, Tuple
import math
from src.core.ecs import System, EntityManager
from src.components.data_components import ActionComponent, MovementComponent, PositionComponent, ResourceComponent
from src.components.skill_component import SkillComponent
from src.core.config_manager import ConfigManager
from src.world.grid import Grid
from src.world.pathfinding import find_path
from src.utils.logger import Logger, LogCategory

class ActionSystem(System):
    def __init__(self, entity_manager: EntityManager, grid: Grid, config_manager: ConfigManager):
        self.entity_manager = entity_manager
        self.grid = grid
        self.config_manager = config_manager

    def update(self, dt: float):
        # Process entities with ActionComponent
        for entity, action_comp in self.entity_manager.get_entities_with(ActionComponent):
            if action_comp.current_action == "idle":
                continue
            
            elif action_comp.current_action == "move":
                self._handle_move(entity, action_comp, dt)
            
            elif action_comp.current_action == "chop":
                self._handle_chop(entity, action_comp, dt)

    def _handle_move(self, entity: int, action_comp: ActionComponent, dt: float):
        move_comp = self.entity_manager.get_component(entity, MovementComponent)
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        
        if not move_comp or not pos_comp:
            action_comp.current_action = "idle"
            return

        # 1. If no path but has target, calculate path
        if not move_comp.path and move_comp.target:
            start = (pos_comp.x, pos_comp.y)
            end = move_comp.target
            # Don't recalc if already there
            if start == end:
                action_comp.current_action = "idle"
                move_comp.target = None
                return
                
            path = find_path(self.grid, start, end)
            if path:
                move_comp.path = path
            else:
                # Path not found
                action_comp.current_action = "idle"
                move_comp.target = None
                Logger.log(LogCategory.AI, f"Entity {entity}: No path to {end}")
                return

        # 2. Follow path
        if move_comp.path:
            target_step = move_comp.path[0]
            
            # Calculate distance (simplified, assuming grid movement)
            # We use a progress float 0..1 for smooth movement between tiles visually (optional)
            # For logic, we just move when progress >= 1
            
            move_comp.progress += move_comp.speed * dt
            
            if move_comp.progress >= 1.0:
                # Move to next tile
                pos_comp.x, pos_comp.y = target_step
                move_comp.path.pop(0)
                move_comp.progress = 0.0
                
                # Re-check if we reached destination
                if not move_comp.path:
                    # If we were moving to a target for an interaction, keep the target in mind
                    # But for pure move action:
                    if action_comp.current_action == "move":
                         action_comp.current_action = "idle"
                         move_comp.target = None

    def _handle_chop(self, entity: int, action_comp: ActionComponent, dt: float):
        target_id = action_comp.target_entity_id
        if target_id is None:
            action_comp.current_action = "idle"
            return

        target_res = self.entity_manager.get_component(target_id, ResourceComponent)
        target_pos = self.entity_manager.get_component(target_id, PositionComponent)
        
        if not target_res or not target_pos:
            # Target gone or invalid
            action_comp.current_action = "idle"
            return

        my_pos = self.entity_manager.get_component(entity, PositionComponent)
        
        # Check distance
        dist = abs(my_pos.x - target_pos.x) + abs(my_pos.y - target_pos.y)
        
        if dist > 1:
            # Too far, move closer
            # We temporarily switch to move logic or handle movement here.
            # Let's set a movement target.
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp:
                # Find a neighbor of target
                # Ideally find closest walkable neighbor
                # Simplified: Set target to target_pos, pathfinding will stop at neighbor if target is occupied/unwalkable?
                # Or we search neighbors.
                neighbors = [
                    (target_pos.x+1, target_pos.y), (target_pos.x-1, target_pos.y),
                    (target_pos.x, target_pos.y+1), (target_pos.x, target_pos.y-1)
                ]
                valid_neighbors = [n for n in neighbors if self.grid.is_walkable(*n)]
                
                if not valid_neighbors:
                    Logger.log(LogCategory.GAMEPLAY, f"Entity {entity}: Cannot reach tree at {target_pos.x},{target_pos.y}")
                    action_comp.current_action = "idle"
                    return
                
                # Pick closest neighbor
                best_n = min(valid_neighbors, key=lambda n: abs(n[0]-my_pos.x) + abs(n[1]-my_pos.y))
                
                move_comp.target = best_n
                # We delegate to _handle_move by keeping action as "chop" but processing move?
                # Or better: Switch state to "move", and queue "chop" for later?
                # For simplicity, let's just call _handle_move logic here if we have a path/target
                
                if not move_comp.path and move_comp.target:
                     # Calculate path
                     move_comp.path = find_path(self.grid, (my_pos.x, my_pos.y), move_comp.target)
                
                if move_comp.path:
                    # Execute move step
                    self._handle_move(entity, action_comp, dt)
                    # Ensure we stay in "chop" state so we check again next frame
                    action_comp.current_action = "chop"
                else:
                    # Stuck
                    action_comp.current_action = "idle"
        else:
            # Close enough, CHOP!
            base_speed = self.config_manager.get("entities.villager.chop_speed", 5.0)
            
            # Check for skill
            skill_comp = self.entity_manager.get_component(entity, SkillComponent)
            multiplier = 1.0
            if skill_comp:
                # Proficiency increases speed. E.g. 0.1 -> +10% speed? 
                # Or let's say multiplier = 1 + skill
                multiplier = 1.0 + skill_comp.skills.get("logging", 0.0)
            
            chop_speed = base_speed * multiplier
            
            target_res.health -= chop_speed * dt
            
            if target_res.health <= 0:
                Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} chopped tree {target_id}!")
                # Chance to increase skill? Not in Phase 2 strictly required but good to have.
                # We'll skip skill learning logic for now as it's not explicitly asked in "check phase 0-2" fix, 
                # but "Learning" is mentioned in README 3.1. 
                # The plan didn't explicitly ask for learning logic, just skill system implementation.
                # I'll leave it out to keep changes focused, or add a simple increment. 
                # Let's add a simple increment if skill exists.
                if skill_comp:
                    current_skill = skill_comp.skills.get("logging", 0.0)
                    if current_skill < 1.0:
                        skill_comp.skills["logging"] = min(1.0, current_skill + 0.01)

                self.entity_manager.destroy_entity(target_id)
                action_comp.current_action = "idle"
                action_comp.target_entity_id = None
