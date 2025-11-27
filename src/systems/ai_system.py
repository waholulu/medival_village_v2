from typing import Optional, Tuple
from src.core.ecs import System, EntityManager
from src.components.data_components import ActionComponent, PositionComponent, JobComponent, InventoryComponent, ResourceComponent, ItemComponent, HungerComponent, TirednessComponent, MovementComponent, CropComponent, TrapComponent, FireComponent
from src.components.skill_component import SkillComponent
from src.systems.job_system import JobSystem, Job
from src.world.grid import Grid, ZONE_STOCKPILE, TERRAIN_WATER
from src.world.zone_manager import ZoneManager
from src.utils.logger import Logger, LogCategory
from src.core.config_manager import ConfigManager

class AISystem(System):
    def __init__(self, entity_manager: EntityManager, job_system: JobSystem, grid: Grid, zone_manager: ZoneManager, config_manager: ConfigManager):
        self.entity_manager = entity_manager
        self.job_system = job_system
        self.grid = grid
        self.zone_manager = zone_manager
        self.config_manager = config_manager
        self._last_job_gen_tick = 0

    def update(self, dt: float):
        # 0. Generate jobs from world state
        self._generate_jobs()

        # 1. Check for urgent needs (hunger, tiredness) - these interrupt jobs
        for entity, action_comp, pos_comp in self.entity_manager.get_entities_with(ActionComponent, PositionComponent):
            hunger_comp = self.entity_manager.get_component(entity, HungerComponent)
            tiredness_comp = self.entity_manager.get_component(entity, TirednessComponent)
            
            # Check urgent hunger (priority 1)
            if hunger_comp and hunger_comp.hunger > 80.0:
                if action_comp.current_action not in ["eat", "move"]:
                    # Interrupt current job if any
                    if self.entity_manager.has_component(entity, JobComponent):
                        job_comp = self.entity_manager.get_component(entity, JobComponent)
                        if job_comp:
                            job = self.job_system.get_job_by_id(job_comp.job_id)
                            if job:
                                self.job_system.complete_job(job.id)
                            self.entity_manager.remove_component(entity, JobComponent)
                    
                    # Try to find and eat food
                    self._find_and_eat_food(entity, action_comp, pos_comp)
                    continue
            
            # Check urgent tiredness (priority 2)
            if tiredness_comp and tiredness_comp.tiredness > 90.0:
                if action_comp.current_action not in ["sleep", "move"]:
                    # Interrupt current job if any
                    if self.entity_manager.has_component(entity, JobComponent):
                        job_comp = self.entity_manager.get_component(entity, JobComponent)
                        if job_comp:
                            job = self.job_system.get_job_by_id(job_comp.job_id)
                            if job:
                                self.job_system.complete_job(job.id)
                            self.entity_manager.remove_component(entity, JobComponent)
                    
                    # Try to find bed and sleep
                    self._find_and_sleep(entity, action_comp, pos_comp)
                    continue

        # 2. Handle entities with jobs
        for entity, job_comp, action_comp, pos_comp in self.entity_manager.get_entities_with(JobComponent, ActionComponent, PositionComponent):
            self._process_job(entity, job_comp, action_comp, pos_comp)

        # 3. Handle idle entities (find jobs)
        for entity, action_comp, skill_comp, pos_comp in self.entity_manager.get_entities_with(ActionComponent, SkillComponent, PositionComponent):
            # Only look for job if no job and idle
            if not self.entity_manager.has_component(entity, JobComponent) and action_comp.current_action == "idle":
                self._find_job(entity, skill_comp, pos_comp)

    def _generate_jobs(self):
        # Only generate jobs every 10 ticks to avoid spam
        from src.utils.logger import Logger
        current_tick = Logger._time_manager.total_ticks if Logger._time_manager else 0
        if current_tick - self._last_job_gen_tick < 10:
            return
        self._last_job_gen_tick = current_tick
        
        # Create Haul jobs for items on ground
        for entity, item_comp, pos_comp in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
            # Check if already has a job
            # Inefficient O(N*M) but fine for now
            has_job = False
            for job in self.job_system.jobs:
                if job.target_entity_id == entity and job.job_type == "haul":
                    has_job = True
                    break
            
            if has_job:
                continue

            # Check if item is already in stockpile
            current_zone = self.zone_manager.grid.get_zone(pos_comp.x, pos_comp.y)
            if current_zone == ZONE_STOCKPILE:
                continue
            
            # Create job
            self.job_system.add_job(Job(
                job_type="haul",
                target_pos=(pos_comp.x, pos_comp.y),
                target_entity_id=entity,
                required_item=item_comp.item_type,
                priority=2 # Higher than chop?
            ))
            Logger.log(LogCategory.AI, f"Created Haul job for {item_comp.item_type} at {pos_comp.x},{pos_comp.y}")
        
        # Create Chop jobs for trees (keep a buffer of available jobs)
        from src.components.tags import IsTree
        existing_chop_jobs = sum(1 for job in self.job_system.jobs if job.job_type == "chop")
        max_chop_jobs = 10  # Keep up to 10 chop jobs available
        
        if existing_chop_jobs < max_chop_jobs:
            for entity, resource_comp, pos_comp in self.entity_manager.get_entities_with(ResourceComponent, PositionComponent):
                # Check if it's a tree
                if not self.entity_manager.has_component(entity, IsTree):
                    continue
                
                # Check if already has a job
                has_job = False
                for job in self.job_system.jobs:
                    if job.target_entity_id == entity and job.job_type == "chop":
                        has_job = True
                        break
                
                if has_job:
                    continue
                
                # Create chop job
                self.job_system.add_job(Job(
                    job_type="chop",
                    target_pos=(pos_comp.x, pos_comp.y),
                    target_entity_id=entity,
                    required_skill="logging",
                    priority=1
                ))
                Logger.log(LogCategory.AI, f"Created Chop job for tree at {pos_comp.x},{pos_comp.y}")
                
                if existing_chop_jobs + 1 >= max_chop_jobs:
                    break  # Stop creating more jobs

    def _find_job(self, entity: int, skill_comp: SkillComponent, pos_comp: PositionComponent):
        # Simple logic: First available job
        # TODO: Check skills
        available_jobs = self.job_system.get_available_jobs()
        
        best_job = None
        # Very basic selection: Take first one that matches skill requirement
        for job in available_jobs:
            if job.required_skill:
                # Check if we have skill? For now, just assume everyone can do everything if level > 0
                # Or just simple check
                if skill_comp.skills.get(job.required_skill, 0.0) > 0:
                    best_job = job
                    break
            else:
                best_job = job
                break
        
        if best_job:
            self.job_system.assign_job(best_job, entity)
            self.entity_manager.add_component(entity, JobComponent(
                job_id=best_job.id,
                job_type=best_job.job_type,
                target_pos=best_job.target_pos,
                target_entity_id=best_job.target_entity_id
            ))
            Logger.log(LogCategory.AI, f"Entity {entity} took job {best_job.job_type}")

    def _process_job(self, entity: int, job_comp: JobComponent, action_comp: ActionComponent, pos_comp: PositionComponent):
        job = self.job_system.get_job_by_id(job_comp.job_id)
        
        # If job is gone/invalid, clear component
        if not job:
            self.entity_manager.remove_component(entity, JobComponent)
            action_comp.current_action = "idle"
            return

        if job.job_type == "chop":
            self._handle_chop_job(entity, job, action_comp, pos_comp)
        elif job.job_type == "haul":
            self._handle_haul_job(entity, job, action_comp, pos_comp)
        elif job.job_type == "plant":
            self._handle_plant_job(entity, job, action_comp, pos_comp)
        elif job.job_type == "harvest":
            self._handle_harvest_job(entity, job, action_comp, pos_comp)
        elif job.job_type == "trap":
            self._handle_trap_job(entity, job, action_comp, pos_comp)
        elif job.job_type == "fish":
            self._handle_fish_job(entity, job, action_comp, pos_comp)
        elif job.job_type == "tend_fire":
            self._handle_tend_fire_job(entity, job, action_comp, pos_comp)

    def _handle_chop_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        # Check if target still exists
        if job.target_entity_id is not None and not self.entity_manager.has_entity(job.target_entity_id):
            # Target destroyed, job done
            self.job_system.complete_job(job.id)
            self.entity_manager.remove_component(entity, JobComponent)
            action_comp.current_action = "idle"
            return

        # If we are currently doing something, let it finish?
        # ActionSystem resets to idle when done with a step (like move)
        if action_comp.current_action != "idle" and action_comp.current_action != "chop":
            return

        # Check distance
        target_pos = job.target_pos
        dist = abs(pos_comp.x - target_pos[0]) + abs(pos_comp.y - target_pos[1])
        
        if dist <= 1:
            # Near enough
            action_comp.current_action = "chop"
            action_comp.target_entity_id = job.target_entity_id
        else:
            # Move to target
            action_comp.current_action = "move"
            # Find neighbor of tree
            # Simple: target the tree pos, ActionSystem handles "move near"
            # But ActionSystem move logic goes TO the tile. We can't walk ON the tree usually.
            # Let's try to find a neighbor here or let ActionSystem handle "move adjacent"
            # For now, set target_pos to tree, assuming ActionSystem handles stopping adjacent?
            # Reading ActionSystem: It pathfinds to target. If target unwalkable, pathfinding fails.
            # So we MUST pick a walkable neighbor.
            
            neighbors = [
                (target_pos[0]+1, target_pos[1]), (target_pos[0]-1, target_pos[1]),
                (target_pos[0], target_pos[1]+1), (target_pos[0], target_pos[1]-1)
            ]
            # Filter walkable
            valid = [n for n in neighbors if self.grid.is_walkable(*n)]
            if valid:
                # Pick closest
                best = min(valid, key=lambda n: abs(n[0]-pos_comp.x) + abs(n[1]-pos_comp.y))
                # Set movement target in MovementComponent?
                # ActionSystem uses MovementComponent.target. 
                # But we should probably set it via ActionComponent? 
                # ActionSystem reads ActionComponent.target_pos? No, it reads ActionComponent.current_action="move" and MovementComponent.target.
                # We need to set MovementComponent.
                from src.components.data_components import MovementComponent
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = best
                    action_comp.current_action = "move"
            else:
                 # Can't reach
                 Logger.log(LogCategory.AI, f"Entity {entity} can't reach tree at {target_pos}")
                 self.job_system.complete_job(job.id) # Cancel job
                 self.entity_manager.remove_component(entity, JobComponent)

    def _handle_haul_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        # 1. Check if we have the item
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        if not inv_comp:
            return # Should have inventory
        
        has_item = inv_comp.items.get(job.required_item, 0) > 0
        
        if not has_item:
            # Go pickup
            if job.target_entity_id is not None and not self.entity_manager.has_entity(job.target_entity_id):
                # Item gone?
                self.job_system.complete_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
                action_comp.current_action = "idle"
                return
            
            target_pos = job.target_pos
            dist = abs(pos_comp.x - target_pos[0]) + abs(pos_comp.y - target_pos[1])
            
            if dist <= 0: # Must be ON the item to pick up? Or adjacent? Let's say ON for items (walkable)
                action_comp.current_action = "pickup"
                action_comp.target_entity_id = job.target_entity_id
            else:
                # Move to item
                 from src.components.data_components import MovementComponent
                 move_comp = self.entity_manager.get_component(entity, MovementComponent)
                 if move_comp:
                     move_comp.target = target_pos
                     action_comp.current_action = "move"
        
        else:
            # Have item, go to stockpile
            stockpile_pos = self.zone_manager.get_nearest_zone_tile((pos_comp.x, pos_comp.y), ZONE_STOCKPILE)
            
            if not stockpile_pos:
                # No stockpile? Drop here or wait?
                Logger.log(LogCategory.AI, f"Entity {entity} has no stockpile to haul to!")
                # Drop it?
                action_comp.current_action = "drop"
                # Complete job?
                self.job_system.complete_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
                return
                
            dist = abs(pos_comp.x - stockpile_pos[0]) + abs(pos_comp.y - stockpile_pos[1])
            
            if dist <= 0:
                action_comp.current_action = "drop"
                # Job done after drop
                # We need to know when drop finishes.
                # ActionSystem sets idle after drop.
                # Next frame we see idle and has_item=False (hopefully)
                # So we will exit this branch and see we don't have item... wait.
                # If we drop, we no longer satisfy "has_item".
                # So we loop back to "not has_item" branch?
                # We need to check if job is complete.
                # Once dropped in stockpile, job is done.
                # We can complete job *after* drop.
                # But we don't know here if drop just happened.
                # Solution: ActionSystem should maybe signal, or we check:
                # If we are AT stockpile AND have item, we drop.
                # Next frame: We are AT stockpile and DON'T have item.
                # But "not has_item" branch thinks we need to go pick up!
                # So we need a state in Job or check if target entity still exists?
                # If we hauled the item, the original target entity (the item on ground) is GONE (picked up).
                # So "not has_item" check: `if job.target_entity_id is not None and not has_entity(...)` will trigger.
                # It will verify item is gone.
                # BUT, we want to mark job as SUCCESS, not failure/cancel.
                pass 
            else:
                from src.components.data_components import MovementComponent
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = stockpile_pos
                    action_comp.current_action = "move"
            
            # Fix for "Drop creates a loop":
            # When we drop at stockpile, the job is essentially done.
            # But we need to execute the "drop" action first.
            # So:
            # Frame 1: Move to stockpile.
            # ...
            # Frame N: At stockpile. Action="drop".
            # Frame N+1: Action="idle". Item in inventory? No.
            # Go to "if not has_item": Target entity (item on ground) ?
            # It was destroyed on pickup.
            # So `not has_entity` is True.
            # We complete job.
            # Perfect! It naturally completes.
    
    def _find_and_eat_food(self, entity: int, action_comp: ActionComponent, pos_comp: PositionComponent):
        """Find food in inventory or on ground and eat it. Uses priority system for food acquisition."""
        
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        skill_comp = self.entity_manager.get_component(entity, SkillComponent)
        hunger_comp = self.entity_manager.get_component(entity, HungerComponent)
        
        # First check inventory for food (highest priority)
        if inv_comp:
            for item_type, amount in inv_comp.items.items():
                if amount > 0:
                    # Check if it's food
                    item_config = self.config_manager.get(f"entities.items.{item_type}", {})
                    if item_config.get("food_value", 0.0) > 0:
                        action_comp.current_action = "eat"
                        return
        
        # No food in inventory, use priority system to find food
        # Priority 1: Food on ground (stockpile or nearby)
        best_food_entity = None
        min_dist = float('inf')
        
        for food_entity, item_comp, food_pos in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
            # Check if it's food
            item_config = self.config_manager.get(f"entities.items.{item_comp.item_type}", {})
            if item_config.get("food_value", 0.0) > 0:
                # Prefer food in stockpile
                food_zone = self.zone_manager.grid.get_zone(food_pos.x, food_pos.y)
                dist = abs(pos_comp.x - food_pos.x) + abs(pos_comp.y - food_pos.y)
                # If in stockpile, reduce distance for priority
                if food_zone == ZONE_STOCKPILE:
                    dist = dist * 0.5  # Prefer stockpile food
                if dist < min_dist:
                    min_dist = dist
                    best_food_entity = food_entity
        
        if best_food_entity and min_dist < 30:  # Within reasonable distance
            # Move to food
            food_pos = self.entity_manager.get_component(best_food_entity, PositionComponent)
            dist = abs(pos_comp.x - food_pos.x) + abs(pos_comp.y - food_pos.y)
            
            if dist <= 0:
                action_comp.current_action = "eat"
                action_comp.target_entity_id = best_food_entity
            else:
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = (food_pos.x, food_pos.y)
                    action_comp.current_action = "move"
                    action_comp.target_entity_id = best_food_entity
            return
        
        # Priority 2: Check traps (if skill is decent and trap is nearby)
        if skill_comp and skill_comp.skills.get("trapping", 0.0) > 0.1:
            best_trap = None
            min_trap_dist = float('inf')
            
            for trap_entity, trap_comp, trap_pos in self.entity_manager.get_entities_with(TrapComponent, PositionComponent):
                if trap_comp.durability > 0:
                    dist = abs(pos_comp.x - trap_pos.x) + abs(pos_comp.y - trap_pos.y)
                    if dist < min_trap_dist and dist < 15:
                        min_trap_dist = dist
                        best_trap = (trap_entity, trap_pos)
            
            if best_trap:
                trap_entity, trap_pos = best_trap
                # Create trap check job or directly check
                action_comp.current_action = "trap"
                action_comp.target_entity_id = trap_entity
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = (trap_pos.x, trap_pos.y)
                return
        
        # Priority 3: Fishing (if skill is decent and water is nearby)
        if skill_comp and skill_comp.skills.get("fishing", 0.0) > 0.1:
            # Find nearest water
            best_water_pos = None
            min_water_dist = float('inf')
            
            # Simple scan for water (in production, would use spatial index)
            for x in range(max(0, pos_comp.x - 20), min(self.grid.width, pos_comp.x + 20)):
                for y in range(max(0, pos_comp.y - 20), min(self.grid.height, pos_comp.y + 20)):
                    if self.grid.get_terrain(x, y) == TERRAIN_WATER:
                        dist = abs(x - pos_comp.x) + abs(y - pos_comp.y)
                        if dist < min_water_dist:
                            min_water_dist = dist
                            best_water_pos = (x, y)
            
            if best_water_pos and min_water_dist < 20:
                # Create fish job
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = best_water_pos
                    action_comp.current_action = "move"
                return
        
        # Priority 4: Create trap (if we have logs and no food available)
        if inv_comp and inv_comp.items.get("log", 0) >= 2:
            # Place trap nearby
            trap_pos = (pos_comp.x + 2, pos_comp.y)  # Simple placement
            if self.grid.is_walkable(*trap_pos):
                action_comp.current_action = "trap"
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = trap_pos
                return
        
        # No food found, stay idle (will starve)
        Logger.log(LogCategory.AI, f"Entity {entity} is hungry but no food found!")
    
    def _find_and_sleep(self, entity: int, action_comp: ActionComponent, pos_comp: PositionComponent):
        """Find residential zone and go to sleep."""
        from src.world.grid import ZONE_RESIDENTIAL
        
        # Find nearest residential zone
        sleep_pos = self.zone_manager.get_nearest_zone_tile((pos_comp.x, pos_comp.y), ZONE_RESIDENTIAL)
        
        if sleep_pos:
            dist = abs(pos_comp.x - sleep_pos[0]) + abs(pos_comp.y - sleep_pos[1])
            
            if dist <= 0:
                # At residential zone, sleep
                action_comp.current_action = "sleep"
            else:
                # Move to residential zone
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = sleep_pos
                    action_comp.current_action = "move"
        else:
            # No residential zone, can't sleep
            Logger.log(LogCategory.AI, f"Entity {entity} is tired but no residential zone found!")
    
    def _handle_plant_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        """Handle plant job - move to farm and plant seed."""
        from src.world.grid import ZONE_FARM
        
        target_pos = job.target_pos
        dist = abs(pos_comp.x - target_pos[0]) + abs(pos_comp.y - target_pos[1])
        
        if dist <= 0:
            # At target, plant
            action_comp.current_action = "plant"
        else:
            # Move to target
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp:
                move_comp.target = target_pos
                action_comp.current_action = "move"
    
    def _handle_harvest_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        """Handle harvest job - move to crop and harvest it."""
        # Check if target still exists
        if job.target_entity_id is not None and not self.entity_manager.has_entity(job.target_entity_id):
            # Target destroyed, job done
            self.job_system.complete_job(job.id)
            self.entity_manager.remove_component(entity, JobComponent)
            action_comp.current_action = "idle"
            return
        
        target_pos = job.target_pos
        dist = abs(pos_comp.x - target_pos[0]) + abs(pos_comp.y - target_pos[1])
        
        if dist <= 1:
            # Near enough, harvest
            action_comp.current_action = "harvest"
            action_comp.target_entity_id = job.target_entity_id
        else:
            # Move to target
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp:
                move_comp.target = target_pos
                action_comp.current_action = "move"

