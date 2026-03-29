from typing import Optional, Tuple
import math
import random
from src.core.ecs import System, EntityManager
from src.components.data_components import ActionComponent, MovementComponent, PositionComponent, ResourceComponent, InventoryComponent, ItemComponent, DurabilityComponent, HungerComponent, MoodComponent, TirednessComponent, SleepStateComponent, CropComponent, ColdComponent, TrapComponent, FireComponent
from src.components.skill_component import SkillComponent
from src.core.config_manager import ConfigManager
from src.core.time_manager import TimeManager
from src.world.grid import Grid
from src.world.pathfinding import find_path
from src.utils.logger import Logger, LogCategory
from src.utils.diagnostic_logger import DiagnosticLogger, DiagLevel

class ActionSystem(System):
    def __init__(self, entity_manager: EntityManager, grid: Grid, config_manager: ConfigManager, time_manager: TimeManager):
        self.entity_manager = entity_manager
        self.grid = grid
        self.config_manager = config_manager
        self.time_manager = time_manager
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
            
            elif action_comp.current_action == "build_drop":
                self._handle_build_drop(entity, action_comp)
                
            elif action_comp.current_action == "build":
                self._handle_build(entity, action_comp, dt)
            
            elif action_comp.current_action == "tend_fire":
                self._handle_tend_fire(entity, action_comp)
                
            elif action_comp.current_action == "build_drop":
                self._handle_build_drop(entity, action_comp)
                
            elif action_comp.current_action == "build":
                self._handle_build(entity, action_comp, dt)

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
                move_comp.path_failed = True
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
                
                old_skill = 0.0
                if skill_comp:
                    old_skill = skill_comp.skills.get("logging", 0.0)
                    current_skill = old_skill
                    if current_skill < 1.0:
                        skill_comp.skills["logging"] = min(1.0, current_skill + 0.01)

                # Diagnostic: tree chopped result
                diag = DiagnosticLogger.get_instance()
                if diag:
                    diag.log_summary(entity, f"Tree chopped (entity#{target_id}) -> dropped 1 log at ({target_pos.x},{target_pos.y})")
                    diag.record_tree_chopped()
                    diag.record_resource_gathered("log", 1)
                    if skill_comp:
                        new_skill = skill_comp.skills.get("logging", 0.0)
                        if new_skill != old_skill:
                            diag.log_detail(entity, f"Skill: logging {old_skill:.2f} -> {new_skill:.2f}")

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

        # Drop all items in inventory
        items_to_drop = [(t, a) for t, a in inv_comp.items.items() if a > 0]
        for item_type, amount in items_to_drop:
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
        
        # If no food in inventory, try eating directly from ground (1 unit only)
        if best_food_value == 0.0 and action_comp.target_entity_id:
            target_item = self.entity_manager.get_component(action_comp.target_entity_id, ItemComponent)
            if target_item:
                item_config = self.config_manager.get(f"entities.items.{target_item.item_type}", {})
                best_food_value = item_config.get("food_value", 0.0)
                if best_food_value > 0.0:
                    # Consume 1 unit directly from the ground stack (don't hoard
                    # the entire pile so other villagers can also eat from it)
                    food_name = target_item.item_type
                    target_item.amount -= 1
                    if target_item.amount <= 0:
                        self.entity_manager.destroy_entity(action_comp.target_entity_id)

                    old_hunger = hunger_comp.hunger
                    old_mood = mood_comp.mood if mood_comp else 0
                    hunger_comp.hunger = max(0.0, hunger_comp.hunger - best_food_value)
                    if mood_comp:
                        mood_comp.mood = min(100.0, mood_comp.mood + best_food_value * 0.5)

                    Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} ate {food_name} (hunger: {hunger_comp.hunger:.1f})")
                    diag = DiagnosticLogger.get_instance()
                    if diag:
                        diag.log_summary(entity, f"Ate {food_name} (value={best_food_value})")
                        if mood_comp:
                            diag.log_detail(entity, f"Hunger: {old_hunger:.1f} -> {hunger_comp.hunger:.1f} | Mood: {old_mood:.1f} -> {mood_comp.mood:.1f}")
                        else:
                            diag.log_detail(entity, f"Hunger: {old_hunger:.1f} -> {hunger_comp.hunger:.1f}")
                        diag.record_food_consumed()

                    action_comp.current_action = "idle"
                    action_comp.target_entity_id = None
                    return
        
        if best_food and best_food_value > 0.0 and inv_comp:
            # Consume food
            if inv_comp.items.get(best_food, 0) > 0:
                old_hunger = hunger_comp.hunger
                old_mood = mood_comp.mood if mood_comp else 0

                inv_comp.items[best_food] -= 1
                if inv_comp.items[best_food] <= 0:
                    del inv_comp.items[best_food]
                
                # Reduce hunger
                hunger_comp.hunger = max(0.0, hunger_comp.hunger - best_food_value)
                
                # Increase mood (food quality affects mood)
                if mood_comp:
                    mood_comp.mood = min(100.0, mood_comp.mood + best_food_value * 0.5)
                
                Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} ate {best_food} (hunger: {hunger_comp.hunger:.1f})")

                # Diagnostic: food consumed
                diag = DiagnosticLogger.get_instance()
                if diag:
                    diag.log_summary(entity, f"Ate {best_food} (value={best_food_value})")
                    diag.log_detail(entity, f"Hunger: {old_hunger:.1f} -> {hunger_comp.hunger:.1f} | Mood: {old_mood:.1f} -> {mood_comp.mood:.1f}" if mood_comp else f"Hunger: {old_hunger:.1f} -> {hunger_comp.hunger:.1f}")
                    diag.record_food_consumed()
        
        action_comp.current_action = "idle"
        action_comp.target_entity_id = None
    
    def _handle_sleep(self, entity: int, action_comp: ActionComponent, dt: float):
        """Handle sleep action - manage sleep state while in residential zone.
        
        Tiredness reduction is handled by NeedsSystem (not here) to avoid
        double-counting. This method only manages sleep state and wake-up.
        """
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
            # Not in residential zone, set to idle and let AISystem handle navigation
            action_comp.current_action = "idle"
            return
        
        # In residential zone, set sleep state
        if not sleep_state:
            sleep_state = SleepStateComponent(is_sleeping=True, sleep_location=(pos_comp.x, pos_comp.y))
            self.entity_manager.add_component(entity, sleep_state)
        else:
            sleep_state.is_sleeping = True
            sleep_state.sleep_location = (pos_comp.x, pos_comp.y)
        
        # Wake up if tiredness is low enough (threshold 5.0 for hysteresis;
        # AI sends to sleep at tiredness > 10, we wake at <= 5 to avoid oscillation)
        if tiredness_comp.tiredness <= 5.0:
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
        seed_item = crop_config.get("seed_item", "seed_wheat")
        
        # Generate food items
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
        
        # Generate seeds (1-2 seeds per harvest to ensure sustainable farming)
        seed_amount = random.randint(1, 2)
        if seed_amount > 0:
            seed_entity = self.entity_manager.create_entity()
            self.entity_manager.add_component(seed_entity, PositionComponent(x=crop_pos.x, y=crop_pos.y))
            self.entity_manager.add_component(seed_entity, ItemComponent(
                item_type=seed_item,
                amount=seed_amount
            ))
        
        # Remove crop
        self.entity_manager.destroy_entity(target_id)
        Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} harvested {crop_comp.crop_type} at ({crop_pos.x}, {crop_pos.y}), got {seed_amount} seeds")

        # Diagnostic: harvest result
        diag = DiagnosticLogger.get_instance()
        if diag:
            yield_str = ", ".join([f"{ft} x{random.randint(ar[0], ar[1])}" for ft, ar in yield_config.items()])
            diag.log_summary(entity, f"Harvested {crop_comp.crop_type} -> {yield_str}, {seed_amount} seeds")
            diag.record_crop_harvested()
            for ft in yield_config:
                diag.record_resource_gathered(ft, 1)
        
        action_comp.current_action = "idle"
        action_comp.target_entity_id = None
    
    def _handle_trap(self, entity: int, action_comp: ActionComponent, dt: float):
        """Handle trap action - check trap or place new trap."""
        
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
            
            trap_interval = self.config_manager.get("entities.trapping.trap_check_interval_hours", 6.0)
            current_hours = self._get_total_game_hours()
            hours_since_last = current_hours - trap_comp.last_check_time
            if hours_since_last < trap_interval:
                action_comp.current_action = "idle"
                return
            
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

                diag = DiagnosticLogger.get_instance()
                if diag:
                    diag.log_summary(entity, f"Trap catch! meat x1 at ({trap_pos.x},{trap_pos.y}), prob={catch_prob:.2f}")
                    diag.record_trap_caught()
                    diag.record_resource_gathered("meat", 1)
                
                # Reduce trap durability
                trap_comp.durability -= 1.0
                if trap_comp.durability <= 0:
                    # Trap broken
                    self.entity_manager.destroy_entity(trap_entity)
                    Logger.log(LogCategory.GAMEPLAY, f"Trap at ({trap_pos.x}, {trap_pos.y}) broke!")
                else:
                    trap_comp.last_check_time = current_hours  # Cooldown before next check
                
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
                trap_comp.last_check_time = current_hours
        
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
                catch_probability=trap_config.get("trap_catch_probability_base", 0.15),
                last_check_time=self._get_total_game_hours()
            ))
            
            Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} placed trap at ({pos_comp.x}, {pos_comp.y})")
        
        action_comp.current_action = "idle"
        action_comp.target_entity_id = None
    
    def _handle_fish(self, entity: int, action_comp: ActionComponent, dt: float):
        """Handle fishing action - fish at water location."""
        from src.world.grid import TERRAIN_WATER
        
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
        best_hours = self.config_manager.get("entities.fishing.fishing_best_hours", [])
        best_hours_bonus = self.config_manager.get("entities.fishing.fishing_best_hours_bonus", 0.3)
        current_hour = self.time_manager.time_of_day

        if best_hours and not self._is_within_time_ranges(current_hour, best_hours):
            # Outside of fishing window, cancel action
            action_comp.current_action = "idle"
            action_comp.target_pos = None
            self._fishing_progress.pop(entity, None)
            return

        if action_comp.target_pos is None:
            action_comp.target_pos = (pos_comp.x, pos_comp.y)
            self._fishing_progress[entity] = 0.0
            return

        progress = self._fishing_progress.get(entity, 0.0) + dt
        self._fishing_progress[entity] = progress

        if progress >= fishing_time:
            # Time to try catching
            base_prob = self.config_manager.get("entities.fishing.fishing_catch_probability_base", 0.2)
            skill_bonus = 0.0
            if skill_comp:
                fishing_skill = skill_comp.skills.get("fishing", 0.0)
                skill_multiplier = self.config_manager.get("entities.fishing.fishing_catch_probability_per_skill", 0.5)
                skill_bonus = fishing_skill * skill_multiplier
            
            time_bonus = best_hours_bonus if best_hours else 0.0
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

                diag = DiagnosticLogger.get_instance()
                if diag:
                    diag.log_summary(entity, f"Fish caught at ({pos_comp.x},{pos_comp.y}), prob={catch_prob:.2f}")
                    diag.record_fish_caught()
                    diag.record_resource_gathered("fish", 1)
                
                # Increase skill
                if skill_comp:
                    old_fish_skill = skill_comp.skills.get("fishing", 0.0)
                    current_skill = old_fish_skill
                    if current_skill < 1.0:
                        skill_comp.skills["fishing"] = min(1.0, current_skill + 0.01)
                    diag2 = DiagnosticLogger.get_instance()
                    if diag2 and skill_comp.skills.get("fishing", 0.0) != old_fish_skill:
                        diag2.log_detail(entity, f"Skill: fishing {old_fish_skill:.2f} -> {skill_comp.skills['fishing']:.2f}")
            
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

    def _handle_build_drop(self, entity: int, action_comp: ActionComponent):
        """Handle dropping a material into a blueprint."""
        from src.components.building_components import BlueprintComponent
        
        target_id = action_comp.target_entity_id
        if target_id is None:
            action_comp.current_action = "idle"
            return
            
        blueprint = self.entity_manager.get_component(target_id, BlueprintComponent)
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        
        if not blueprint or not inv_comp:
            action_comp.current_action = "idle"
            return
            
        # Find which material we should drop
        # (The AI system queued this job because a specific material was needed)
        # We just look at what's still needed and what we have
        material_to_drop = None
        amount_to_drop = 0
        
        for mat_type, count_needed in blueprint.required_materials.items():
            current = blueprint.current_materials.get(mat_type, 0)
            if current < count_needed:
                # We need this material. Do we have it?
                if inv_comp.items.get(mat_type, 0) > 0:
                    material_to_drop = mat_type
                    # Drop whatever we have, or up to what's needed
                    amount_to_drop = min(inv_comp.items[mat_type], count_needed - current)
                    break
                    
        if material_to_drop and amount_to_drop > 0:
            # Transfer item
            inv_comp.items[material_to_drop] -= amount_to_drop
            if inv_comp.items[material_to_drop] <= 0:
                del inv_comp.items[material_to_drop]
                
            blueprint.current_materials[material_to_drop] = blueprint.current_materials.get(material_to_drop, 0) + amount_to_drop
            
            Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} dropped {amount_to_drop} {material_to_drop} into blueprint for {blueprint.building_type}")
            
            # The AI system's job complete logic is not directly called here since ActionSystem doesn't know the job ID.
            # But AI System will detect job is no longer valid (or action is idle) and will clean it up.
            # However, for haul jobs we usually want to explicitly complete them so we don't have dangling jobs.
            # Since AISystem does the job cleanup when job is missing from entity, we should clear the JobComponent.
            # The AI system handles completing haul_to_blueprint jobs automatically if the material need is fulfilled,
            # but to be safe we just clear the current action and the AI system will re-evaluate.
            
        action_comp.current_action = "idle"
        action_comp.target_entity_id = None
        
        # Clear the job so the AI knows we finished this specific haul task
        from src.components.data_components import JobComponent
        from src.systems.job_system import JobSystem
        job_comp = self.entity_manager.get_component(entity, JobComponent)
        if job_comp:
            # Ideally we'd have access to job_system here to call complete_job, but we don't.
            # Removing the component makes the AI system realize the job is dead and clean it up next tick.
            self.entity_manager.remove_component(entity, JobComponent)
            
    def _handle_build(self, entity: int, action_comp: ActionComponent, dt: float):
        """Handle adding work points to a blueprint."""
        from src.components.building_components import BlueprintComponent
        
        target_id = action_comp.target_entity_id
        if target_id is None:
            action_comp.current_action = "idle"
            return
            
        blueprint = self.entity_manager.get_component(target_id, BlueprintComponent)
        if not blueprint:
            action_comp.current_action = "idle"
            return
            
        # Calculate build speed (base + skill)
        base_speed = self.config_manager.get("entities.villager.build_speed", 10.0)
        skill_comp = self.entity_manager.get_component(entity, SkillComponent)
        multiplier = 1.0
        
        if skill_comp:
             # Use logging skill as proxy for building stuff for now
             multiplier = 1.0 + skill_comp.skills.get("logging", 0.0)
             
        build_speed = base_speed * multiplier
        blueprint.work_completed += build_speed * dt
        
        # Skill gain
        if skill_comp:
            current_skill = skill_comp.skills.get("logging", 0.0)
            if current_skill < 1.0:
                 # Slow skill gain
                 skill_comp.skills["logging"] = min(1.0, current_skill + 0.05 * dt)
                 
        # If complete, the BuildingSystem will handle the transformation to a BuildingComponent.
        # We just keep working until it is done or removed.
        if blueprint.work_completed >= blueprint.work_required:
            action_comp.current_action = "idle"
            action_comp.target_entity_id = None
            
            # Remove job component to force clean up
            from src.components.data_components import JobComponent
            job_comp = self.entity_manager.get_component(entity, JobComponent)
            if job_comp:
                self.entity_manager.remove_component(entity, JobComponent)
    
    def _get_total_game_hours(self) -> float:
        """Return cumulative game hours for cooldown calculations."""
        if not self.time_manager:
            return 0.0
        return self.time_manager.day * 24.0 + self.time_manager.time_of_day

    def _is_within_time_ranges(self, hour: float, ranges: list) -> bool:
        """Check if current hour falls within any configured [start, end) pairs."""
        if not ranges or len(ranges) < 2:
            return True
        for i in range(0, len(ranges) - 1, 2):
            start = ranges[i]
            end = ranges[i + 1]
            if start <= end:
                if start <= hour < end:
                    return True
            else:
                # Overnight window (e.g., 22 -> 4)
                if hour >= start or hour < end:
                    return True
        return False

    def _handle_build_drop(self, entity: int, action_comp: ActionComponent):
        from src.components.building_components import BlueprintComponent
        from src.components.data_components import JobComponent
        
        target_entity = action_comp.target_entity_id
        if target_entity is None:
            action_comp.current_action = "idle"
            return
            
        blueprint = self.entity_manager.get_component(target_entity, BlueprintComponent)
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        job_comp = self.entity_manager.get_component(entity, JobComponent)
        
        if not blueprint or not inv_comp or not job_comp:
            action_comp.current_action = "idle"
            return
            
        placed_any = False
        for mat_type, needed in blueprint.required_materials.items():
            current = blueprint.current_materials.get(mat_type, 0)
            if current < needed and inv_comp.items.get(mat_type, 0) > 0:
                amount_to_give = min(needed - current, inv_comp.items[mat_type])
                blueprint.current_materials[mat_type] = current + amount_to_give
                inv_comp.items[mat_type] -= amount_to_give
                if inv_comp.items[mat_type] <= 0:
                    del inv_comp.items[mat_type]
                placed_any = True
                Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} added {amount_to_give} {mat_type} to blueprint at {target_entity}")
                break
                
        if placed_any:
            pass # Job is completed naturally when entity becomes idle
            
        action_comp.current_action = "idle"
        action_comp.target_entity_id = None
        
    def _handle_build(self, entity: int, action_comp: ActionComponent, dt: float):
        from src.components.building_components import BlueprintComponent
        
        target_entity = action_comp.target_entity_id
        if target_entity is None:
            action_comp.current_action = "idle"
            return
            
        blueprint = self.entity_manager.get_component(target_entity, BlueprintComponent)
        if not blueprint:
            action_comp.current_action = "idle"
            return
            
        skill_comp = self.entity_manager.get_component(entity, SkillComponent)
        build_speed = 10.0 # base speed
        if skill_comp:
            build_speed += skill_comp.skills.get("logging", 0.1) * 20.0
            
        work_done = build_speed * dt
        blueprint.work_completed += work_done
        
        if blueprint.work_completed >= blueprint.work_required:
            action_comp.current_action = "idle"
            action_comp.target_entity_id = None
