from typing import Optional, Tuple
import math
from src.core.ecs import System, EntityManager
from src.components.data_components import ActionComponent, MovementComponent, PositionComponent, ResourceComponent, InventoryComponent, ItemComponent, DurabilityComponent, HungerComponent, MoodComponent, TirednessComponent, SleepStateComponent, CropComponent
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
                
            elif action_comp.current_action == "pickup":
                self._handle_pickup(entity, action_comp)
                
            elif action_comp.current_action == "drop":
                self._handle_drop(entity, action_comp)
            
            elif action_comp.current_action == "eat":
                self._handle_eat(entity, action_comp)
            
            elif action_comp.current_action == "sleep":
                self._handle_sleep(entity, action_comp, dt)
            
            elif action_comp.current_action == "plant":
                self._handle_plant(entity, action_comp)
            
            elif action_comp.current_action == "harvest":
                self._handle_harvest(entity, action_comp)

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
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp:
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
                multiplier = 1.0 + skill_comp.skills.get("logging", 0.0)
            
            # Check for tool (in inventory or as entity)
            tool_efficiency = 1.0
            inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
            tool_entity_id = None
            
            # Look for tool in inventory (simplified: check for "axe_stone" item)
            if inv_comp and "axe_stone" in inv_comp.items and inv_comp.items["axe_stone"] > 0:
                # Tool is in inventory, we'll consume durability on a tool entity if it exists
                # For now, we'll just use the tool efficiency from config
                tool_config = self.config_manager.get("entities.tools.axe_stone", {})
                tool_efficiency = tool_config.get("efficiency", 1.0)
            
            # Also check for tool as separate entity (future: tools can be separate entities)
            # For now, we'll handle durability consumption if tool is an entity
            
            chop_speed = base_speed * multiplier * tool_efficiency
            
            target_res.health -= chop_speed * dt
            
            # Consume tool durability if using tool
            if tool_efficiency > 1.0 or inv_comp and "axe_stone" in inv_comp.items:
                # Find tool entity or consume from inventory
                # For simplicity, we'll consume durability on a per-chop basis
                # In a more complex system, tools would be separate entities with DurabilityComponent
                durability_loss = self.config_manager.get("entities.tools.axe_stone.durability_loss_per_use", 1.0)
                # For now, we'll just log it - full tool system would track durability per tool
            
            if target_res.health <= 0:
                Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} chopped tree {target_id}!")
                
                # Spawn logs
                drops = target_res.drops.get("log", [1, 1])
                # Simplified: always spawn 1 log entity for now, or match drops logic
                # We spawn an Item entity
                log_entity = self.entity_manager.create_entity()
                self.entity_manager.add_component(log_entity, PositionComponent(x=target_pos.x, y=target_pos.y))
                self.entity_manager.add_component(log_entity, ItemComponent(item_type="log", amount=1))
                
                if skill_comp:
                    current_skill = skill_comp.skills.get("logging", 0.0)
                    if current_skill < 1.0:
                        skill_comp.skills["logging"] = min(1.0, current_skill + 0.01)

                self.entity_manager.destroy_entity(target_id)
                action_comp.current_action = "idle"
                action_comp.target_entity_id = None

    def _handle_pickup(self, entity: int, action_comp: ActionComponent):
        target_id = action_comp.target_entity_id
        item_comp = self.entity_manager.get_component(target_id, ItemComponent)
        
        if not item_comp:
            action_comp.current_action = "idle"
            return
            
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        if inv_comp:
            # Add to inventory
            current_amount = inv_comp.items.get(item_comp.item_type, 0)
            inv_comp.items[item_comp.item_type] = current_amount + item_comp.amount
            
            Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} picked up {item_comp.amount} {item_comp.item_type}")
            
            self.entity_manager.destroy_entity(target_id)
            
        action_comp.current_action = "idle"
        action_comp.target_entity_id = None

    def _handle_drop(self, entity: int, action_comp: ActionComponent):
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        
        if not inv_comp or not pos_comp:
            action_comp.current_action = "idle"
            return

        # Drop everything? Or what is specified?
        # For now, drop the first thing in inventory as a simple test
        if inv_comp.items:
            item_type, amount = list(inv_comp.items.items())[0]
            if amount > 0:
                # Create item entity
                item_entity = self.entity_manager.create_entity()
                self.entity_manager.add_component(item_entity, PositionComponent(x=pos_comp.x, y=pos_comp.y))
                self.entity_manager.add_component(item_entity, ItemComponent(item_type=item_type, amount=amount))
                
                del inv_comp.items[item_type]
                Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} dropped {amount} {item_type}")
                
        action_comp.current_action = "idle"
    
    def _handle_eat(self, entity: int, action_comp: ActionComponent):
        """Handle eating action - consume food from inventory or ground."""
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        hunger_comp = self.entity_manager.get_component(entity, HungerComponent)
        mood_comp = self.entity_manager.get_component(entity, MoodComponent)
        
        if not hunger_comp:
            action_comp.current_action = "idle"
            return
        
        # Find food in inventory
        best_food = None
        best_food_value = 0.0
        
        if inv_comp:
            # Check all items in inventory for food_value
            for item_type, amount in inv_comp.items.items():
                if amount > 0:
                    # Get food value from config
                    item_config = self.config_manager.get(f"entities.items.{item_type}", {})
                    food_value = item_config.get("food_value", 0.0)
                    
                    if food_value > best_food_value:
                        best_food = item_type
                        best_food_value = food_value
        
        # If no food in inventory, check if we're trying to eat from ground
        if best_food_value == 0.0 and action_comp.target_entity_id:
            target_item = self.entity_manager.get_component(action_comp.target_entity_id, ItemComponent)
            if target_item:
                item_config = self.config_manager.get(f"entities.items.{target_item.item_type}", {})
                best_food_value = item_config.get("food_value", 0.0)
                if best_food_value > 0.0:
                    # Pick up and eat
                    self._handle_pickup(entity, action_comp)
                    # After pickup, food should be in inventory, so retry
                    inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
                    if inv_comp and target_item.item_type in inv_comp.items:
                        best_food = target_item.item_type
                    else:
                        action_comp.current_action = "idle"
                        return
        
        if best_food and best_food_value > 0.0 and inv_comp:
            # Consume food
            if inv_comp.items.get(best_food, 0) > 0:
                inv_comp.items[best_food] -= 1
                if inv_comp.items[best_food] <= 0:
                    del inv_comp.items[best_food]
                
                # Reduce hunger
                hunger_comp.hunger = max(0.0, hunger_comp.hunger - best_food_value)
                
                # Increase mood (food quality affects mood)
                if mood_comp:
                    mood_comp.mood = min(100.0, mood_comp.mood + best_food_value * 0.5)
                
                Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} ate {best_food} (hunger: {hunger_comp.hunger:.1f})")
        
        action_comp.current_action = "idle"
        action_comp.target_entity_id = None
    
    def _handle_sleep(self, entity: int, action_comp: ActionComponent, dt: float):
        """Handle sleep action - reduce tiredness while in residential zone."""
        from src.world.grid import ZONE_RESIDENTIAL
        
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        tiredness_comp = self.entity_manager.get_component(entity, TirednessComponent)
        sleep_state = self.entity_manager.get_component(entity, SleepStateComponent)
        
        if not pos_comp or not tiredness_comp:
            action_comp.current_action = "idle"
            return
        
        # Check if in residential zone
        current_zone = self.grid.get_zone(pos_comp.x, pos_comp.y)
        if current_zone != ZONE_RESIDENTIAL:
            # Not in residential zone, try to move there
            # For now, just set to idle and let AISystem handle finding residential zone
            action_comp.current_action = "idle"
            return
        
        # In residential zone, sleep
        if not sleep_state:
            sleep_state = SleepStateComponent(is_sleeping=True, sleep_location=(pos_comp.x, pos_comp.y))
            self.entity_manager.add_component(entity, sleep_state)
        else:
            sleep_state.is_sleeping = True
            sleep_state.sleep_location = (pos_comp.x, pos_comp.y)
        
        # Reduce tiredness (handled by NeedsSystem, but we can also do it here)
        day_length = self.config_manager.get("simulation.day_length_seconds", 600.0)
        hours_per_second = 24.0 / day_length
        hours_passed = dt * hours_per_second
        tiredness_per_hour_resting = self.config_manager.get("entities.villager.needs.tiredness_per_hour_resting", -10.0)
        tiredness_change = tiredness_per_hour_resting * hours_passed
        tiredness_comp.tiredness = max(0.0, tiredness_comp.tiredness + tiredness_change)
        
        # Wake up if tiredness is low enough
        if tiredness_comp.tiredness <= 10.0:
            if sleep_state:
                sleep_state.is_sleeping = False
            action_comp.current_action = "idle"
            Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} woke up (tiredness: {tiredness_comp.tiredness:.1f})")
    
    def _handle_plant(self, entity: int, action_comp: ActionComponent):
        """Handle plant action - plant seed in farm zone."""
        from src.world.grid import ZONE_FARM
        
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        
        if not pos_comp:
            action_comp.current_action = "idle"
            return
        
        # Check if in farm zone
        current_zone = self.grid.get_zone(pos_comp.x, pos_comp.y)
        if current_zone != ZONE_FARM:
            action_comp.current_action = "idle"
            return
        
        # Check if there's already a crop here
        for crop_entity, crop_comp, crop_pos in self.entity_manager.get_entities_with(CropComponent, PositionComponent):
            if crop_pos.x == pos_comp.x and crop_pos.y == pos_comp.y:
                # Already has crop
                action_comp.current_action = "idle"
                return
        
        # Find seed in inventory (simplified: look for seed_wheat)
        if inv_comp and "seed_wheat" in inv_comp.items and inv_comp.items["seed_wheat"] > 0:
            # Plant the seed
            inv_comp.items["seed_wheat"] -= 1
            if inv_comp.items["seed_wheat"] <= 0:
                del inv_comp.items["seed_wheat"]
            
            # Create crop entity
            crop_entity = self.entity_manager.create_entity()
            self.entity_manager.add_component(crop_entity, PositionComponent(x=pos_comp.x, y=pos_comp.y))
            self.entity_manager.add_component(crop_entity, CropComponent(
                crop_type="wheat",
                growth_progress=0.0,
                state="seed"
            ))
            
            Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} planted wheat at ({pos_comp.x}, {pos_comp.y})")
        
        action_comp.current_action = "idle"
    
    def _handle_harvest(self, entity: int, action_comp: ActionComponent):
        """Handle harvest action - harvest ripe crop and generate food."""
        target_id = action_comp.target_entity_id
        if target_id is None:
            action_comp.current_action = "idle"
            return
        
        crop_comp = self.entity_manager.get_component(target_id, CropComponent)
        crop_pos = self.entity_manager.get_component(target_id, PositionComponent)
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        
        if not crop_comp or not crop_pos or not pos_comp:
            action_comp.current_action = "idle"
            return
        
        # Check distance
        dist = abs(pos_comp.x - crop_pos.x) + abs(pos_comp.y - crop_pos.y)
        if dist > 1:
            action_comp.current_action = "idle"
            return
        
        # Check if ripe
        if crop_comp.state != "ripe":
            action_comp.current_action = "idle"
            return
        
        # Get crop config
        crop_config = self.config_manager.get(f"entities.crops.{crop_comp.crop_type}", {})
        yield_config = crop_config.get("yield", {"food_wheat": [2, 4]})
        
        # Generate food items
        import random
        for food_type, amount_range in yield_config.items():
            amount = random.randint(amount_range[0], amount_range[1])
            if amount > 0:
                # Create food item entity
                food_entity = self.entity_manager.create_entity()
                self.entity_manager.add_component(food_entity, PositionComponent(x=crop_pos.x, y=crop_pos.y))
                self.entity_manager.add_component(food_entity, ItemComponent(
                    item_type=food_type,
                    amount=amount,
                    food_value=self.config_manager.get(f"entities.items.{food_type}.food_value", 0.0)
                ))
        
        # Remove crop
        self.entity_manager.destroy_entity(target_id)
        Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} harvested {crop_comp.crop_type} at ({crop_pos.x}, {crop_pos.y})")
        
        action_comp.current_action = "idle"
        action_comp.target_entity_id = None
