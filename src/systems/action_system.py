from typing import Optional, Tuple
import math
from src.core.ecs import System, EntityManager
from src.components.data_components import ActionComponent, MovementComponent, PositionComponent, ResourceComponent, InventoryComponent, ItemComponent, DurabilityComponent, HungerComponent, MoodComponent, TirednessComponent, SleepStateComponent, CropComponent, ColdComponent, TrapComponent, FireComponent
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
        self._fishing_progress = {}  # Track fishing progress per entity

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
            
            elif action_comp.current_action == "trap":
                self._handle_trap(entity, action_comp, dt)
            
            elif action_comp.current_action == "fish":
                self._handle_fish(entity, action_comp, dt)
            
            elif action_comp.current_action == "create_fire":
                self._handle_create_fire(entity, action_comp)
            
            elif action_comp.current_action == "tend_fire":
                self._handle_tend_fire(entity, action_comp)

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
    
    def _handle_trap(self, entity: int, action_comp: ActionComponent, dt: float):
        """Handle trap action - check trap or place new trap."""
        from src.core.time_manager import TimeManager
        import random
        
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        skill_comp = self.entity_manager.get_component(entity, SkillComponent)
        
        if not pos_comp:
            action_comp.current_action = "idle"
            return
        
        # Check if we're placing a trap or checking an existing one
        if action_comp.target_entity_id:
            # Checking existing trap
            trap_entity = action_comp.target_entity_id
            trap_comp = self.entity_manager.get_component(trap_entity, TrapComponent)
            trap_pos = self.entity_manager.get_component(trap_entity, PositionComponent)
            
            if not trap_comp or not trap_pos:
                action_comp.current_action = "idle"
                return
            
            # Check distance
            dist = abs(pos_comp.x - trap_pos.x) + abs(pos_comp.y - trap_pos.y)
            if dist > 1:
                action_comp.current_action = "idle"
                return
            
            # Check if enough time has passed since last check
            # For now, we'll allow checking traps immediately (simplified)
            # In a full system, we'd track last_check_time properly
            
            # Calculate catch probability
            base_prob = self.config_manager.get("entities.trapping.trap_catch_probability_base", 0.15)
            skill_bonus = 0.0
            if skill_comp:
                trapping_skill = skill_comp.skills.get("trapping", 0.0)
                skill_multiplier = self.config_manager.get("entities.trapping.trap_catch_probability_per_skill", 0.5)
                skill_bonus = trapping_skill * skill_multiplier
            
            catch_prob = base_prob * (1.0 + skill_bonus)
            
            # Try to catch
            if random.random() < catch_prob:
                # Success! Generate meat
                meat_entity = self.entity_manager.create_entity()
                self.entity_manager.add_component(meat_entity, PositionComponent(x=trap_pos.x, y=trap_pos.y))
                self.entity_manager.add_component(meat_entity, ItemComponent(
                    item_type="meat",
                    amount=1,
                    food_value=self.config_manager.get("entities.items.meat.food_value", 40.0)
                ))
                Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} caught meat in trap at ({trap_pos.x}, {trap_pos.y})")
                
                # Reduce trap durability
                trap_comp.durability -= 1.0
                if trap_comp.durability <= 0:
                    # Trap broken
                    self.entity_manager.destroy_entity(trap_entity)
                    Logger.log(LogCategory.GAMEPLAY, f"Trap at ({trap_pos.x}, {trap_pos.y}) broke!")
                else:
                    trap_comp.last_check_time = 0.0  # Reset check time
                
                # Increase skill
                if skill_comp:
                    current_skill = skill_comp.skills.get("trapping", 0.0)
                    if current_skill < 1.0:
                        skill_comp.skills["trapping"] = min(1.0, current_skill + 0.01)
            else:
                # No catch, but still reduce durability slightly
                trap_comp.durability -= 0.1
                if trap_comp.durability <= 0:
                    self.entity_manager.destroy_entity(trap_entity)
                    Logger.log(LogCategory.GAMEPLAY, f"Trap at ({trap_pos.x}, {trap_pos.y}) broke!")
                trap_comp.last_check_time = 0.0
        
        else:
            # Placing new trap
            # Check if we have logs
            if not inv_comp or inv_comp.items.get("log", 0) < 2:
                action_comp.current_action = "idle"
                return
            
            # Check if there's already a trap here
            for trap_entity, trap_comp, trap_pos in self.entity_manager.get_entities_with(TrapComponent, PositionComponent):
                if trap_pos.x == pos_comp.x and trap_pos.y == pos_comp.y:
                    action_comp.current_action = "idle"
                    return
            
            # Place trap
            inv_comp.items["log"] -= 2
            if inv_comp.items["log"] <= 0:
                del inv_comp.items["log"]
            
            trap_entity = self.entity_manager.create_entity()
            self.entity_manager.add_component(trap_entity, PositionComponent(x=pos_comp.x, y=pos_comp.y))
            trap_config = self.config_manager.get("entities.trapping", {})
            self.entity_manager.add_component(trap_entity, TrapComponent(
                trap_type="basic_trap",
                durability=trap_config.get("trap_durability", 10.0),
                max_durability=trap_config.get("trap_durability", 10.0),
                catch_probability=trap_config.get("trap_catch_probability_base", 0.15)
            ))
            
            Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} placed trap at ({pos_comp.x}, {pos_comp.y})")
        
        action_comp.current_action = "idle"
        action_comp.target_entity_id = None
    
    def _handle_fish(self, entity: int, action_comp: ActionComponent, dt: float):
        """Handle fishing action - fish at water location."""
        from src.world.grid import TERRAIN_WATER
        import random
        
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        skill_comp = self.entity_manager.get_component(entity, SkillComponent)
        
        if not pos_comp:
            action_comp.current_action = "idle"
            return
        
        # Check if we're at water
        if self.grid.get_terrain(pos_comp.x, pos_comp.y) != TERRAIN_WATER:
            # Check adjacent tiles
            neighbors = [
                (pos_comp.x+1, pos_comp.y), (pos_comp.x-1, pos_comp.y),
                (pos_comp.x, pos_comp.y+1), (pos_comp.x, pos_comp.y-1)
            ]
            has_water = False
            for nx, ny in neighbors:
                if 0 <= nx < self.grid.width and 0 <= ny < self.grid.height:
                    if self.grid.get_terrain(nx, ny) == TERRAIN_WATER:
                        has_water = True
                        break
            
            if not has_water:
                action_comp.current_action = "idle"
                return
        
        # Check if we have a fishing progress tracker (simplified: use action_comp.target_pos as progress)
        # For now, we'll use a simple time-based approach
        fishing_time = self.config_manager.get("entities.fishing.fishing_time_per_attempt_seconds", 30.0)
        day_length = self.config_manager.get("simulation.day_length_seconds", 10.0)
        fishing_time_game = fishing_time / day_length  # Convert to game time
        
        # Use target_pos to track if we've started fishing
        if action_comp.target_pos is None:
            # Start fishing
            action_comp.target_pos = (pos_comp.x, pos_comp.y)  # Mark that we started
            self._fishing_progress[entity] = 0.0
            return
        
        # Accumulate time
        if entity not in self._fishing_progress:
            self._fishing_progress[entity] = 0.0
        
        self._fishing_progress[entity] += dt
        
        if self._fishing_progress[entity] >= fishing_time_game:
            # Time to try catching
            base_prob = self.config_manager.get("entities.fishing.fishing_catch_probability_base", 0.2)
            skill_bonus = 0.0
            if skill_comp:
                fishing_skill = skill_comp.skills.get("fishing", 0.0)
                skill_multiplier = self.config_manager.get("entities.fishing.fishing_catch_probability_per_skill", 0.5)
                skill_bonus = fishing_skill * skill_multiplier
            
            # Check if it's a good time to fish
            time_bonus = 0.0
            # We'd need time_manager here, simplified for now
            best_hours = self.config_manager.get("entities.fishing.fishing_best_hours", [5.0, 7.0, 18.0, 20.0])
            best_hours_bonus = self.config_manager.get("entities.fishing.fishing_best_hours_bonus", 0.3)
            # For now, assume random time bonus
            
            catch_prob = base_prob * (1.0 + skill_bonus + time_bonus)
            
            if random.random() < catch_prob:
                # Success! Generate fish
                fish_entity = self.entity_manager.create_entity()
                self.entity_manager.add_component(fish_entity, PositionComponent(x=pos_comp.x, y=pos_comp.y))
                self.entity_manager.add_component(fish_entity, ItemComponent(
                    item_type="fish",
                    amount=1,
                    food_value=self.config_manager.get("entities.items.fish.food_value", 35.0)
                ))
                Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} caught fish at ({pos_comp.x}, {pos_comp.y})")
                
                # Increase skill
                if skill_comp:
                    current_skill = skill_comp.skills.get("fishing", 0.0)
                    if current_skill < 1.0:
                        skill_comp.skills["fishing"] = min(1.0, current_skill + 0.01)
            
            # Reset progress
            if entity in self._fishing_progress:
                del self._fishing_progress[entity]
            action_comp.current_action = "idle"
            action_comp.target_pos = None
    
    def _handle_create_fire(self, entity: int, action_comp: ActionComponent):
        """Handle create fire action - create fire entity at location."""
        from src.world.grid import ZONE_RESIDENTIAL
        
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        
        if not pos_comp:
            action_comp.current_action = "idle"
            return
        
        # Check if we have logs
        fire_cost = self.config_manager.get("entities.fire.fire_creation_cost_logs", 3)
        if not inv_comp or inv_comp.items.get("log", 0) < fire_cost:
            action_comp.current_action = "idle"
            return
        
        # Check if there's already a fire here
        for fire_entity, fire_comp, fire_pos in self.entity_manager.get_entities_with(FireComponent, PositionComponent):
            if fire_pos.x == pos_comp.x and fire_pos.y == pos_comp.y:
                action_comp.current_action = "idle"
                return
        
        # Create fire
        inv_comp.items["log"] -= fire_cost
        if inv_comp.items["log"] <= 0:
            del inv_comp.items["log"]
        
        fire_config = self.config_manager.get("entities.fire", {})
        fire_entity = self.entity_manager.create_entity()
        self.entity_manager.add_component(fire_entity, PositionComponent(x=pos_comp.x, y=pos_comp.y))
        self.entity_manager.add_component(fire_entity, FireComponent(
            fuel_remaining=fire_cost * 10.0,  # Initial fuel
            warmth_radius=fire_config.get("fire_warmth_radius", 5),
            fuel_consumption_per_hour=fire_config.get("fire_fuel_consumption_per_hour", 1.0)
        ))
        
        Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} created fire at ({pos_comp.x}, {pos_comp.y})")
        
        action_comp.current_action = "idle"
    
    def _handle_tend_fire(self, entity: int, action_comp: ActionComponent):
        """Handle tend fire action - add fuel to fire."""
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        
        if not pos_comp or not inv_comp:
            action_comp.current_action = "idle"
            return
        
        # Find fire at this location
        fire_entity = None
        fire_comp = None
        for fe, fc, fp in self.entity_manager.get_entities_with(FireComponent, PositionComponent):
            if fp.x == pos_comp.x and fp.y == pos_comp.y:
                fire_entity = fe
                fire_comp = fc
                break
        
        if not fire_comp:
            action_comp.current_action = "idle"
            return
        
        # Check if we have logs
        if inv_comp.items.get("log", 0) < 1:
            action_comp.current_action = "idle"
            return
        
        # Add fuel
        inv_comp.items["log"] -= 1
        if inv_comp.items["log"] <= 0:
            del inv_comp.items["log"]
        
        fire_comp.fuel_remaining += 10.0  # Add fuel
        Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} added fuel to fire at ({pos_comp.x}, {pos_comp.y})")
        
        action_comp.current_action = "idle"
