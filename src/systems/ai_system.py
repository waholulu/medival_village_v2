from typing import Optional, Tuple
from src.core.ecs import System, EntityManager
from src.components.data_components import ActionComponent, PositionComponent, JobComponent, InventoryComponent, ResourceComponent, ItemComponent, HungerComponent, TirednessComponent, MovementComponent, CropComponent, TrapComponent, FireComponent, RoutineComponent, SleepStateComponent, NeedLockComponent
from src.components.skill_component import SkillComponent
from src.systems.job_system import JobSystem, Job
from src.world.grid import Grid, ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL, TERRAIN_WATER, ZONE_NONE
from src.world.zone_manager import ZoneManager
from src.utils.logger import Logger, LogCategory
from src.utils.diagnostic_logger import DiagnosticLogger, DiagLevel
from src.components.tags import IsTree, IsVillager, IsPlayer
from src.core.config_manager import ConfigManager
from src.core.time_manager import TimeManager

class AISystem(System):
    def __init__(self, entity_manager: EntityManager, job_system: JobSystem, grid: Grid, zone_manager: ZoneManager, config_manager: ConfigManager, time_manager: TimeManager = None):
        self.entity_manager = entity_manager
        self.job_system = job_system
        self.grid = grid
        self.zone_manager = zone_manager
        self.config_manager = config_manager
        self.time_manager = time_manager
        
        self._failed_jobs_cooldown: Dict[str, float] = {}
        
        self._last_job_gen_tick = 0
        self._no_food_cooldown = {}  # entity -> tick when "no food" was last logged

    def _has_food_available(self, entity: int, pos_comp) -> bool:
        """Quick check: is there any food the entity could eat (in inventory or nearby)?"""
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        if inv_comp:
            for item_type, amount in inv_comp.items.items():
                if amount > 0:
                    item_config = self.config_manager.get(f"entities.items.{item_type}", {})
                    if item_config.get("food_value", 0.0) > 0:
                        return True
        
        # Check food on ground (entire map — food is survival-critical)
        for food_entity, item_comp, food_pos in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
            item_config = self.config_manager.get(f"entities.items.{item_comp.item_type}", {})
            if item_config.get("food_value", 0.0) > 0:
                return True
        return False

    def _release_current_job(self, entity: int):
        """Release current job back to available pool (don't destroy it)."""
        if self.entity_manager.has_component(entity, JobComponent):
            job_comp = self.entity_manager.get_component(entity, JobComponent)
            if job_comp:
                self.job_system.release_job(job_comp.job_id)
                self.entity_manager.remove_component(entity, JobComponent)

    def _clear_sleep_state(self, entity: int):
        """Clear SleepStateComponent.is_sleeping flag when a villager is no longer sleeping."""
        sleep_state = self.entity_manager.get_component(entity, SleepStateComponent)
        if sleep_state and sleep_state.is_sleeping:
            sleep_state.is_sleeping = False
            diag = DiagnosticLogger.get_instance()
            if diag:
                diag.log_detail(entity, f"SleepState cleared (is_sleeping -> False)")

    def _clear_movement(self, entity: int):
        """Clear current movement path and target so a new destination can be set cleanly."""
        move_comp = self.entity_manager.get_component(entity, MovementComponent)
        if move_comp:
            move_comp.path = []
            move_comp.target = None

    def _is_moving_toward_food(self, entity: int, action_comp) -> bool:
        """Check if entity is currently moving toward a food source."""
        if action_comp.current_action != "move":
            return False
        if action_comp.target_entity_id:
            target_item = self.entity_manager.get_component(action_comp.target_entity_id, ItemComponent)
            if target_item:
                item_config = self.config_manager.get(f"entities.items.{target_item.item_type}", {})
                if item_config.get("food_value", 0.0) > 0:
                    return True
        return False

    def _is_moving_toward_sleep(self, entity: int) -> bool:
        """Check if entity is currently moving toward a residential zone for sleep."""
        move_comp = self.entity_manager.get_component(entity, MovementComponent)
        if move_comp and move_comp.target:
            target_zone = self.grid.get_zone(move_comp.target[0], move_comp.target[1])
            if target_zone == ZONE_RESIDENTIAL:
                return True
        return False

    # ---------- Need-lock helpers (anti-oscillation) ----------

    def _get_need_lock(self, entity: int, current_tick: int):
        """Return active need-lock type ('eat'/'sleep') or None if expired/absent."""
        lock_comp = self.entity_manager.get_component(entity, NeedLockComponent)
        if lock_comp:
            if current_tick < lock_comp.expiry_tick:
                return lock_comp.lock_type
            else:
                self.entity_manager.remove_component(entity, NeedLockComponent)
        return None

    def _set_need_lock(self, entity: int, lock_type: str, current_tick: int, duration: int = 600):
        """Lock entity to a need-driven behaviour for *duration* ticks to prevent oscillation."""
        lock_comp = self.entity_manager.get_component(entity, NeedLockComponent)
        if lock_comp:
            lock_comp.lock_type = lock_type
            lock_comp.expiry_tick = current_tick + duration
        else:
            self.entity_manager.add_component(entity, NeedLockComponent(lock_type=lock_type, expiry_tick=current_tick + duration))

    def _clear_need_lock(self, entity: int):
        """Remove any active need lock."""
        self.entity_manager.remove_component(entity, NeedLockComponent)

    def _nearest_food_distance(self, entity: int, pos_comp) -> float:
        """Return Manhattan distance to nearest reachable food, or None if none."""
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        if inv_comp:
            for item_type, amount in inv_comp.items.items():
                if amount > 0:
                    item_config = self.config_manager.get(f"entities.items.{item_type}", {})
                    if item_config.get("food_value", 0.0) > 0:
                        return 0  # Food already in inventory
        best = None
        for food_entity, item_comp, food_pos in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
            item_config = self.config_manager.get(f"entities.items.{item_comp.item_type}", {})
            if item_config.get("food_value", 0.0) > 0:
                dist = abs(pos_comp.x - food_pos.x) + abs(pos_comp.y - food_pos.y)
                if best is None or dist < best:
                    best = dist
        return best

    def update(self, dt: float):
        # 0. Generate jobs from world state
        self._generate_jobs()
        self._plan_buildings()

        current_tick = self.time_manager.total_ticks if self.time_manager else 0

        # 1. Unified Entity Processing (SleepState, Sleep Schedule, Urgent Needs)
        for entity, action_comp in self.entity_manager.get_entities_with(ActionComponent):
            # 0.1 Blanket SleepState clearing: any entity NOT sleeping must have is_sleeping=False
            if action_comp.current_action != "sleep":
                self._clear_sleep_state(entity)

            pos_comp = self.entity_manager.get_component(entity, PositionComponent)
            if not pos_comp:
                continue

            routine_comp = self.entity_manager.get_component(entity, RoutineComponent)

            # 0.5. Enforce sleep schedule: release jobs and redirect to sleep during SLEEPING routine
            if routine_comp and routine_comp.current_state == "SLEEPING":
                # If moving and already on a residential tile, stop and sleep immediately
                # BUT don't intercept if the villager is urgently seeking food
                if action_comp.current_action == "move":
                    current_zone = self.grid.get_zone(pos_comp.x, pos_comp.y)
                    if current_zone == ZONE_RESIDENTIAL and not self._is_moving_toward_food(entity, action_comp):
                        self._release_current_job(entity)
                        self._clear_movement(entity)
                        action_comp.current_action = "sleep"
                        diag = DiagnosticLogger.get_instance()
                        if diag:
                            diag.log_detail(entity, "AI: Arrived at residential zone during SLEEPING, starting sleep")
                        continue

                # If has an active job during sleep time, release it so villager can sleep
                if self.entity_manager.has_component(entity, JobComponent):
                    self._release_current_job(entity)
                    self._clear_movement(entity)
                    action_comp.current_action = "idle"
                    diag = DiagnosticLogger.get_instance()
                    if diag:
                        diag.log_detail(entity, "AI: Released job for sleep time")

            # 1. Check for urgent needs (hunger, tiredness) - these interrupt jobs
            hunger_comp = self.entity_manager.get_component(entity, HungerComponent)
            tiredness_comp = self.entity_manager.get_component(entity, TirednessComponent)

            # --- Need lock: prevent eat/sleep oscillation ---
            active_lock = self._get_need_lock(entity, current_tick)

            # Check routine-based eating (priority 0.5 - less urgent but proactive)
            should_eat_by_routine = False
            if routine_comp and routine_comp.current_state == "EATING" and hunger_comp:
                if hunger_comp.hunger > 30.0:
                    should_eat_by_routine = True

            # Check urgent hunger (priority 1)
            is_urgently_hungry = hunger_comp and hunger_comp.hunger > 50.0

            # Only try to eat if food actually exists (prevents infinite job thrashing)
            food_available = False
            if should_eat_by_routine or is_urgently_hungry:
                food_available = self._has_food_available(entity, pos_comp)

            # --- Anti-oscillation: suppress hunger while sleeping / locked-to-sleep / chopping ---
            hunger_suppressed = False
            # Suppress hunger during active chop -- only extreme hunger (>80) interrupts
            if action_comp.current_action == "chop" and hunger_comp and hunger_comp.hunger <= 80.0:
                hunger_suppressed = True
            if action_comp.current_action == "sleep" and hunger_comp and hunger_comp.hunger <= 95.0:
                hunger_suppressed = True
            if active_lock == "sleep" and hunger_comp and hunger_comp.hunger <= 95.0:
                hunger_suppressed = True
            # During SLEEPING routine, don't trigger routine-based meal eating
            # (urgent hunger >50 still works; active sleep/lock handle the rest)
            if routine_comp and routine_comp.current_state == "SLEEPING":
                should_eat_by_routine = False
            # If heading to residential for sleep, suppress hunger so they
            # reach the bed first (only near-death hunger >90 interrupts the journey)
            if self._is_moving_toward_sleep(entity) and hunger_comp and hunger_comp.hunger <= 90.0:
                hunger_suppressed = True

            if (should_eat_by_routine or is_urgently_hungry) and food_available and not hunger_suppressed:
                already_seeking_food = (
                    action_comp.current_action == "eat"
                    or self._is_moving_toward_food(entity, action_comp)
                )
                if not already_seeking_food:
                    diag = DiagnosticLogger.get_instance()
                    if diag:
                        if is_urgently_hungry:
                            diag.log_summary(entity, f"AI: Urgent hunger={hunger_comp.hunger:.1f}, interrupting {action_comp.current_action}")
                        elif should_eat_by_routine:
                            diag.log_detail(entity, f"AI: Routine meal time, hunger={hunger_comp.hunger:.1f}")

                    self._clear_sleep_state(entity)
                    self._release_current_job(entity)
                    self._clear_movement(entity)

                    # Lock to eating — tiredness cannot interrupt for 600 ticks
                    self._set_need_lock(entity, "eat", current_tick, 600)

                    self._find_and_eat_food(entity, action_comp, pos_comp)
                    continue
            elif is_urgently_hungry and not food_available:
                last_logged = self._no_food_cooldown.get(entity, 0)
                if current_tick - last_logged >= 60:
                    self._no_food_cooldown[entity] = current_tick
                    Logger.log(LogCategory.AI, f"Entity {entity} is hungry but no food found!")
                    diag = DiagnosticLogger.get_instance()
                    if diag:
                        h_val = hunger_comp.hunger if hunger_comp else 0
                        diag.log_summary(entity, f"AI: !! NO FOOD FOUND (hunger={h_val:.1f}) - will starve")

            # --- Anti-oscillation: suppress tiredness while eating / locked-to-eat ---
            tiredness_suppressed = False
            if active_lock == "eat" and tiredness_comp:
                tiredness_suppressed = True  # fully suppress while eat-locked
            if self._is_moving_toward_food(entity, action_comp) and tiredness_comp and tiredness_comp.tiredness <= 98.0:
                tiredness_suppressed = True

            # Check urgent tiredness (priority 2) - runs even if hungry but no food
            if tiredness_comp and tiredness_comp.tiredness > 90.0 and not tiredness_suppressed:
                already_seeking_sleep = (
                    action_comp.current_action == "sleep"
                    or (action_comp.current_action == "move" and self._is_moving_toward_sleep(entity))
                )
                if not already_seeking_sleep:
                    diag = DiagnosticLogger.get_instance()
                    if diag:
                        diag.log_summary(entity, f"AI: Urgent tiredness={tiredness_comp.tiredness:.1f}, interrupting {action_comp.current_action}")

                    self._clear_sleep_state(entity)
                    self._release_current_job(entity)
                    self._clear_movement(entity)

                    # Lock to sleeping — hunger cannot interrupt for 600 ticks
                    self._set_need_lock(entity, "sleep", current_tick, 600)

                    self._find_and_sleep(entity, action_comp, pos_comp)
                    continue

        # 2. Handle entities with jobs
        for entity, job_comp, action_comp, pos_comp in self.entity_manager.get_entities_with(JobComponent, ActionComponent, PositionComponent):
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp and move_comp.path_failed:
                move_comp.path_failed = False
                diag = DiagnosticLogger.get_instance()
                if diag:
                    diag.log_detail(entity, f"AI: Job #{job_comp.job_id} failed - path unreachable")
                
                # Add to failed cooldown
                self._failed_jobs_cooldown[job_comp.job_id] = current_tick + 600
                self._release_current_job(entity)
                self._clear_movement(entity)
                action_comp.current_action = "idle"
                continue

            self._process_job(entity, job_comp, action_comp, pos_comp)

        # 3. Handle idle entities (find jobs, respecting routine state)
        for entity, action_comp, skill_comp, pos_comp in self.entity_manager.get_entities_with(ActionComponent, SkillComponent, PositionComponent):
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp and move_comp.path_failed:
                move_comp.path_failed = False
                diag = DiagnosticLogger.get_instance()
                if diag:
                    diag.log_detail(entity, "AI: Navigation to non-job target failed.")

            # Clear stale sleep state: if not sleeping but flag is still set
            if action_comp.current_action != "sleep":
                self._clear_sleep_state(entity)
            
            # Only look for job if no job and idle
            if not self.entity_manager.has_component(entity, JobComponent) and action_comp.current_action == "idle":
                # Food-seeking persistence: if the villager just arrived at a food
                # target (e.g. was walking to food during EATING, routine changed to
                # WORKING mid-trip), finish eating before taking a new job.
                if action_comp.target_entity_id is not None:
                    target_item = self.entity_manager.get_component(action_comp.target_entity_id, ItemComponent)
                    if target_item:
                        item_config = self.config_manager.get(f"entities.items.{target_item.item_type}", {})
                        if item_config.get("food_value", 0.0) > 0:
                            target_pos_comp = self.entity_manager.get_component(action_comp.target_entity_id, PositionComponent)
                            if target_pos_comp:
                                dist_to_food = abs(pos_comp.x - target_pos_comp.x) + abs(pos_comp.y - target_pos_comp.y)
                                if dist_to_food <= 1:
                                    action_comp.current_action = "eat"
                                    continue

                routine_comp = self.entity_manager.get_component(entity, RoutineComponent)
                routine_state = routine_comp.current_state if routine_comp else "WORKING"
                
                if routine_state == "SLEEPING":
                    # Deposit all carried items before heading to bed
                    self._deposit_all_items(entity, action_comp)
                    # During sleep hours, go to sleep if any tiredness remains
                    tiredness_comp = self.entity_manager.get_component(entity, TirednessComponent)
                    if tiredness_comp and tiredness_comp.tiredness > 0.0:
                        self._find_and_sleep(entity, action_comp, pos_comp)
                    # ALWAYS continue -- never fall through to _find_job during sleep hours
                    continue
                
                elif routine_state == "EATING":
                    # During meal times, keep eating until hunger is very low
                    hunger_comp = self.entity_manager.get_component(entity, HungerComponent)
                    if hunger_comp and hunger_comp.hunger > 10.0:
                        if self._has_food_available(entity, pos_comp):
                            self._find_and_eat_food(entity, action_comp, pos_comp)
                            continue
                    # Even if hunger is low or no food, don't work during meal time
                    continue
                
                elif routine_state == "SOCIALIZING":
                    # During social hours, don't actively seek work.
                    # Deposit all items so they're available for the community.
                    self._deposit_all_items(entity, action_comp)
                    continue
                
                # WORKING or RESTING or fallthrough from EATING: find a job
                # But first: if carrying raw resources (logs) and at stockpile, deposit them
                inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
                if inv_comp and inv_comp.items:
                    current_zone = self.grid.get_zone(pos_comp.x, pos_comp.y)
                    if current_zone == ZONE_STOCKPILE:
                        if self._deposit_resources(entity):
                            continue

                self._find_job(entity, skill_comp, pos_comp)

    def _generate_jobs(self):
        # Only generate jobs every 10 ticks to avoid spam
        current_tick = self.time_manager.total_ticks if self.time_manager else 0
        if current_tick - self._last_job_gen_tick < 10:
            return
        self._last_job_gen_tick = current_tick
        
        # Create Haul jobs for items on ground
        for entity, item_comp, pos_comp in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
            # Check if already has a haul job (O(1) lookup via index)
            if self.job_system.has_job_for_entity(entity, "haul"):
                continue

            # Check if item is already in stockpile
            current_zone = self.zone_manager.grid.get_zone(pos_comp.x, pos_comp.y)
            if current_zone == ZONE_STOCKPILE:
                continue
            
            # Prioritize food hauling (food is survival-critical)
            item_config = self.config_manager.get(f"entities.items.{item_comp.item_type}", {})
            is_food = item_config.get("food_value", 0.0) > 0
            haul_priority = 5 if is_food else 2

            # Create job
            self.job_system.add_job(Job(
                job_type="haul",
                target_pos=(pos_comp.x, pos_comp.y),
                target_entity_id=entity,
                required_item=item_comp.item_type,
                priority=haul_priority
            ))
            Logger.log(LogCategory.AI, f"Created Haul job for {item_comp.item_type} at {pos_comp.x},{pos_comp.y}")
        
        # Create Chop jobs for trees (keep a buffer of available jobs)
        existing_chop_jobs = sum(1 for job in self.job_system.jobs if job.job_type == "chop")
        max_chop_jobs = 10  # Keep up to 10 chop jobs available
        
        if existing_chop_jobs < max_chop_jobs:
            for entity, resource_comp, pos_comp in self.entity_manager.get_entities_with(ResourceComponent, PositionComponent):
                # Check if it's a tree
                if not self.entity_manager.has_component(entity, IsTree):
                    continue
                
                # Check if already has a chop job (O(1) lookup via index)
                if self.job_system.has_job_for_entity(entity, "chop"):
                    continue
                
                # Create chop job (priority 4: wood is essential for fire/building)
                self.job_system.add_job(Job(
                    job_type="chop",
                    target_pos=(pos_comp.x, pos_comp.y),
                    target_entity_id=entity,
                    required_skill="logging",
                    priority=4
                ))
                Logger.log(LogCategory.AI, f"Created Chop job for tree at {pos_comp.x},{pos_comp.y}")
                existing_chop_jobs += 1
                
                if existing_chop_jobs >= max_chop_jobs:
                    break  # Stop creating more jobs

    def _plan_buildings(self):
        """Autonomously plan buildings if there is a need."""
        current_tick = self.time_manager.total_ticks if self.time_manager else 0
        if not hasattr(self, '_last_blueprint_gen_tick'):
            self._last_blueprint_gen_tick = 0
            
        if current_tick - self._last_blueprint_gen_tick < 300: # Check every 300 ticks (5 seconds)
            return
        self._last_blueprint_gen_tick = current_tick

        villager_count = sum(1 for e, _ in self.entity_manager.get_entities_with(IsVillager)) + \
                         sum(1 for e, _ in self.entity_manager.get_entities_with(IsPlayer))
        
        Logger.info(f"[DEBUG _plan_buildings] Running at tick {current_tick}. Villagers: {villager_count}")

        from src.components.building_components import BlueprintComponent, BuildingComponent
        house_count = 0
        storage_count = 0
        
        for e, pos in self.entity_manager.get_entities_with(PositionComponent):
            b_type = None
            if self.entity_manager.has_component(e, BlueprintComponent):
                b_type = self.entity_manager.get_component(e, BlueprintComponent).building_type
            elif self.entity_manager.has_component(e, BuildingComponent):
                b_type = self.entity_manager.get_component(e, BuildingComponent).building_type
                
            if b_type == "house":
                house_count += 1
            elif b_type == "storage":
                storage_count += 1

        # We assume 1 house sleeps 2 villagers.
        Logger.info(f"[DEBUG _plan_buildings] tick: {current_tick} villagers: {villager_count} houses: {house_count} storage: {storage_count}")
        if house_count * 2 < villager_count:
            if self._try_place_blueprint("house", ZONE_RESIDENTIAL):
                Logger.info("[DEBUG _plan_buildings] placed house!")
                return # Only place one per cycle

        # Check for storage need: if there are many items on the ground not in stockpile/storage
        items_on_ground = 0
        for e, item, pos in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
            zone = self.grid.get_zone(pos.x, pos.y)
            if zone != ZONE_STOCKPILE:
                items_on_ground += 1
                
        if items_on_ground > 15 and storage_count == 0:
            # If there's a lot of mess, build at least one storage
            if self._try_place_blueprint("storage", ZONE_STOCKPILE):
                Logger.info("[DEBUG _plan_buildings] placed storage!")
                return

    def _try_place_blueprint(self, blueprint_type: str, preferred_zone: int) -> bool:
        b_config = self.config_manager.get(f"entities.buildings.{blueprint_type}", {})
        if not b_config:
            Logger.info(f"Failed to find config for {blueprint_type}")
            return False
            
        # Find all tiles of preferred zone
        valid_tiles = []
        for x in range(self.grid.width):
            for y in range(self.grid.height):
                if self.grid.get_zone(x, y) == preferred_zone and self.grid.is_walkable(x, y):
                    valid_tiles.append((x, y))
                    
        # If no preferred zone, find grassy area near center
        if not valid_tiles:
             center_x, center_y = self.grid.width // 2, self.grid.height // 2
             for r in range(3, 20):
                 for dx in range(-r, r+1):
                     for dy in range(-r, r+1):
                         x, y = center_x + dx, center_y + dy
                         if 0 <= x < self.grid.width and 0 <= y < self.grid.height:
                             if self.grid.get_terrain(x, y) == 0 and self.grid.is_walkable(x, y): # 0 is Grass
                                 if self.grid.get_zone(x, y) == ZONE_NONE:
                                     valid_tiles.append((x, y))
                 if valid_tiles:
                     break
                     
        if not valid_tiles:
            return False

        import random
        random.shuffle(valid_tiles)
        
        from src.components.building_components import BlueprintComponent, BuildingComponent
        for tx, ty in valid_tiles:
             # Check if occupied by another blueprint/building or tree
             occupied = False
             for e, pos in self.entity_manager.get_entities_with(PositionComponent):
                 if pos.x == tx and pos.y == ty:
                     if self.entity_manager.has_component(e, BlueprintComponent) or self.entity_manager.has_component(e, BuildingComponent) or self.entity_manager.has_component(e, IsTree):
                         occupied = True
                         break
             if not occupied:
                 # Place it
                 blueprint_entity = self.entity_manager.create_entity()
                 self.entity_manager.add_component(blueprint_entity, PositionComponent(x=tx, y=ty))
                 cost = b_config.get("cost", {})
                 work = b_config.get("work_required", 100.0)
                 self.entity_manager.add_component(blueprint_entity, BlueprintComponent(
                     building_type=blueprint_type,
                     required_materials=cost,
                     work_required=work
                 ))
                 Logger.info(f"AI autonomously placed {blueprint_type} blueprint at ({tx}, {ty})")
                 return True
                 
        return False

    def _find_job(self, entity: int, skill_comp: SkillComponent, pos_comp: PositionComponent):
        available_jobs = self.job_system.get_available_jobs()
        
        # Get hunger for distance-based filtering
        hunger_comp = self.entity_manager.get_component(entity, HungerComponent)
        current_hunger = hunger_comp.hunger if hunger_comp else 0.0
        
        # Pre-check: are seeds available for plant jobs? (avoids take/release churn)
        seeds_available = False
        inv_comp_check = self.entity_manager.get_component(entity, InventoryComponent)
        if inv_comp_check and inv_comp_check.items.get("seed_wheat", 0) > 0:
            seeds_available = True
        else:
            for _, item_comp_s, _ in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
                if item_comp_s.item_type == "seed_wheat" and item_comp_s.amount > 0:
                    seeds_available = True
                    break
        
        best_job = None
        best_score = -float('inf')
        
        for job in available_jobs:
            # Check skill requirement
            if job.required_skill:
                if skill_comp.skills.get(job.required_skill, 0.0) <= 0:
                    continue
            
            # Plant job: skip if no seeds available anywhere
            if job.job_type == "plant" and not seeds_available:
                continue
            
            # Check if job is on cooldown due to recent failure
            if job.id in self._failed_jobs_cooldown:
                if self.time_manager.total_ticks < self._failed_jobs_cooldown[job.id]:
                    continue
                else:
                    del self._failed_jobs_cooldown[job.id]
                    
            # Calculate distance to job target
            dist = abs(pos_comp.x - job.target_pos[0]) + abs(pos_comp.y - job.target_pos[1])
            
            # If hungry, gradually restrict job distance to stay near food.
            # At hunger 30 max_dist=25, at hunger 50 max_dist=15, at hunger 70 max_dist=5
            if current_hunger > 30.0:
                max_dist = max(5, int(35 - current_hunger * 0.4))
                if dist > max_dist:
                    continue
            
            # Score: higher priority and closer distance is better
            # Skill bonus: villagers with matching skills prefer those jobs
            skill_bonus = 0.0
            if job.required_skill:
                skill_level = skill_comp.skills.get(job.required_skill, 0.0)
                skill_bonus = skill_level * 2.0  # e.g. logging 0.6 -> +1.2 bonus
            
            # Seed bonus: mild preference for plant jobs when already carrying seeds
            seed_bonus = 0.0
            if job.job_type == "plant":
                inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
                if inv_comp and inv_comp.items.get("seed_wheat", 0) > 0:
                    seed_bonus = 1.5

            # Harvest bonus: ripe crops are time-critical (food supply)
            harvest_bonus = 0.0
            if job.job_type == "harvest":
                harvest_bonus = 3.0

            score = job.priority * 2.0 - dist * 0.1 + skill_bonus + seed_bonus + harvest_bonus
            
            if score > best_score:
                best_score = score
                best_job = job
        
        if best_job:
            self.job_system.assign_job(best_job, entity)
            self.entity_manager.add_component(entity, JobComponent(
                job_id=best_job.id,
                job_type=best_job.job_type,
                target_pos=best_job.target_pos,
                target_entity_id=best_job.target_entity_id
            ))
            Logger.log(LogCategory.AI, f"Entity {entity} took job {best_job.job_type}")
            diag = DiagnosticLogger.get_instance()
            if diag:
                skills_str = ", ".join([f"{k}:{v:.2f}" for k, v in skill_comp.skills.items()])
                diag.log_detail(entity, f"AI: Assigned job #{best_job.id}: {best_job.job_type} at {best_job.target_pos}, skills: {{{skills_str}}}")

    def _process_job(self, entity: int, job_comp: JobComponent, action_comp: ActionComponent, pos_comp: PositionComponent):
        job = self.job_system.get_job_by_id(job_comp.job_id)
        
        # If job is gone/invalid, clear component
        if not job:
            self.entity_manager.remove_component(entity, JobComponent)
            action_comp.current_action = "idle"
            return

        # Cancel over-distance jobs when hunger is rising (prevent starvation from long walks)
        if action_comp.current_action == "move" and job.target_pos:
            hunger_comp = self.entity_manager.get_component(entity, HungerComponent)
            if hunger_comp and hunger_comp.hunger > 40.0:
                remaining_dist = abs(pos_comp.x - job.target_pos[0]) + abs(pos_comp.y - job.target_pos[1])
                if remaining_dist > 15:
                    diag = DiagnosticLogger.get_instance()
                    if diag:
                        diag.log_detail(entity, f"AI: Releasing distant job {job.job_type} (dist={remaining_dist}, hunger={hunger_comp.hunger:.1f})")
                    self._release_current_job(entity)
                    self._clear_movement(entity)
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
        elif job.job_type == "haul_to_blueprint":
            self._handle_haul_to_blueprint_job(entity, job, action_comp, pos_comp)
        elif job.job_type == "build":
            self._handle_build_job(entity, job, action_comp, pos_comp)

    def _auto_pickup_nearby_items(self, entity: int, target_pos, pos_comp):
        """Auto-pickup items at a position if the villager is within 1 tile."""
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        if not inv_comp or not target_pos:
            return

        items_to_destroy = []
        for item_entity, item_comp, item_pos in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
            if item_pos.x != target_pos[0] or item_pos.y != target_pos[1]:
                continue
            dist = abs(pos_comp.x - item_pos.x) + abs(pos_comp.y - item_pos.y)
            if dist > 1:
                continue
            current = inv_comp.items.get(item_comp.item_type, 0)
            inv_comp.items[item_comp.item_type] = current + item_comp.amount
            items_to_destroy.append((item_entity, item_comp.item_type, item_comp.amount))

        for item_entity, item_type, amount in items_to_destroy:
            self.entity_manager.destroy_entity(item_entity)
            Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} picked up {amount} {item_type}")
            diag = DiagnosticLogger.get_instance()
            if diag:
                diag.log_detail(entity, f"Auto-pickup: {amount} {item_type}")

    def _handle_chop_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        # Check if target still exists
        if job.target_entity_id is not None and not self.entity_manager.has_entity(job.target_entity_id):
            # Target destroyed (tree chopped down), job done
            self.job_system.complete_job(job.id)
            self.entity_manager.remove_component(entity, JobComponent)
            diag = DiagnosticLogger.get_instance()
            if diag:
                diag.log_summary(entity, f"Job completed: chop (tree destroyed)")

            # Auto-pickup: collect items dropped at the chop location
            self._auto_pickup_nearby_items(entity, job.target_pos, pos_comp)

            # If carrying items, head to stockpile to deposit
            inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
            if inv_comp and inv_comp.items:
                stockpile_pos = self.zone_manager.get_nearest_zone_tile(
                    (pos_comp.x, pos_comp.y), ZONE_STOCKPILE
                )
                if stockpile_pos:
                    move_comp = self.entity_manager.get_component(entity, MovementComponent)
                    if move_comp:
                        move_comp.target = stockpile_pos
                        action_comp.current_action = "move"
                        return

            action_comp.current_action = "idle"
            return

        # If already chopping, let ActionSystem continue the work
        if action_comp.current_action == "chop":
            return

        # If doing something else (like moving), let it finish
        if action_comp.current_action != "idle":
            return

        # Check distance
        target_pos = job.target_pos
        dist = abs(pos_comp.x - target_pos[0]) + abs(pos_comp.y - target_pos[1])
        
        if dist <= 1:
            # Near enough, start chopping - keep job active until tree is destroyed
            action_comp.current_action = "chop"
            action_comp.target_entity_id = job.target_entity_id
            # DON'T complete job here - let it complete when tree entity is destroyed
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
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = best
                    action_comp.current_action = "move"
            else:
                 # Can't reach
                Logger.log(LogCategory.AI, f"Entity {entity} can't reach tree at {target_pos}")
                self.job_system.complete_job(job.id)  # Cancel job
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
            
            if dist <= 1:  # Adjacent or on the item
                action_comp.current_action = "pickup"
                action_comp.target_entity_id = job.target_entity_id
            else:
                # Move to item
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
            
            if dist == 0:  # Must be ON the stockpile tile to drop
                action_comp.current_action = "drop"
                # Mark haul job as complete after initiating drop.
                # The item will be placed at the stockpile by ActionSystem.
                # After drop, action goes idle, item is on ground in stockpile zone.
                self.job_system.complete_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
            else:
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = stockpile_pos
                    action_comp.current_action = "move"    
    def _deposit_resources(self, entity: int) -> bool:
        """Deposit raw resource items (not seeds, not food) from inventory at current
        position. Used when idle at stockpile during work hours. Returns True if any
        items were deposited."""
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        if not inv_comp or not inv_comp.items:
            return False
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        if not pos_comp:
            return False

        to_drop = []
        for item_type, amount in inv_comp.items.items():
            if amount <= 0:
                continue
            item_config = self.config_manager.get(f"entities.items.{item_type}", {})
            if item_config.get("food_value", 0.0) > 0:
                continue  # keep food for eating
            if item_config.get("item_type", "") == "seed":
                continue  # keep seeds for planting
            to_drop.append((item_type, amount))

        for item_type, amount in to_drop:
            item_entity = self.entity_manager.create_entity()
            self.entity_manager.add_component(item_entity, PositionComponent(x=pos_comp.x, y=pos_comp.y))
            self.entity_manager.add_component(item_entity, ItemComponent(item_type=item_type, amount=amount))
            del inv_comp.items[item_type]
            diag = DiagnosticLogger.get_instance()
            if diag:
                diag.log_detail(entity, f"Deposited {amount} {item_type} at stockpile")

        return len(to_drop) > 0

    def _deposit_all_items(self, entity: int, action_comp: ActionComponent):
        """Deposit all items from inventory to ground at current position.
        Called when entering non-work routines (SLEEPING, SOCIALIZING) so
        items are available for the community via haul jobs."""
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        if not inv_comp or not inv_comp.items:
            return
        pos_comp = self.entity_manager.get_component(entity, PositionComponent)
        if not pos_comp:
            return

        to_drop = [(item_type, amount) for item_type, amount in inv_comp.items.items() if amount > 0]

        for item_type, amount in to_drop:
            item_entity = self.entity_manager.create_entity()
            self.entity_manager.add_component(item_entity, PositionComponent(x=pos_comp.x, y=pos_comp.y))
            self.entity_manager.add_component(item_entity, ItemComponent(item_type=item_type, amount=amount))
            del inv_comp.items[item_type]
            diag = DiagnosticLogger.get_instance()
            if diag:
                diag.log_detail(entity, f"Deposited {amount} {item_type} (off-duty)")

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
                        diag = DiagnosticLogger.get_instance()
                        if diag:
                            diag.log_detail(entity, f"AI: Food search -> found {item_type} x{amount} in inventory")
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
        
        if best_food_entity and min_dist < 80:  # Within map range (food is survival-critical)
            # Move to food
            food_pos = self.entity_manager.get_component(best_food_entity, PositionComponent)
            food_item = self.entity_manager.get_component(best_food_entity, ItemComponent)
            dist = abs(pos_comp.x - food_pos.x) + abs(pos_comp.y - food_pos.y)

            diag = DiagnosticLogger.get_instance()
            if diag and food_item:
                zone = self.zone_manager.grid.get_zone(food_pos.x, food_pos.y)
                zone_str = "stockpile" if zone == ZONE_STOCKPILE else "ground"
                diag.log_detail(entity, f"AI: Food search -> found {food_item.item_type} on {zone_str} at ({food_pos.x},{food_pos.y}), dist={dist}")

            if dist <= 1:  # Adjacent or on the food
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
        
        # No food found - this shouldn't normally be reached since we pre-check
        # in update(), but keep as fallback
        pass
    
    def _find_and_sleep(self, entity: int, action_comp: ActionComponent, pos_comp: PositionComponent):
        """Find residential zone and go to sleep."""
        
        # Check if already standing on a residential tile
        current_zone = self.grid.get_zone(pos_comp.x, pos_comp.y)
        if current_zone == ZONE_RESIDENTIAL:
            action_comp.current_action = "sleep"
            return

        # Find nearest residential zone tile
        sleep_pos = self.zone_manager.get_nearest_zone_tile((pos_comp.x, pos_comp.y), ZONE_RESIDENTIAL)
        
        if sleep_pos:
            # Move to residential zone (must be ON the tile, not just adjacent)
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp:
                move_comp.target = sleep_pos
                action_comp.current_action = "move"
        else:
            # No residential zone, can't sleep
            Logger.log(LogCategory.AI, f"Entity {entity} is tired but no residential zone found!")
    
    def _handle_plant_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        """Handle plant job - move to farm and plant seed."""
        
        # Check if a crop already exists at the target position (job already done)
        target_pos = job.target_pos
        for crop_entity, crop_comp, crop_pos in self.entity_manager.get_entities_with(CropComponent, PositionComponent):
            if crop_pos.x == target_pos[0] and crop_pos.y == target_pos[1]:
                # Crop already planted here, job is done
                self.job_system.complete_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
                action_comp.current_action = "idle"
                diag = DiagnosticLogger.get_instance()
                if diag:
                    diag.log_detail(entity, f"Plant job completed: crop already at {target_pos}")
                return
        
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        has_seed = inv_comp and inv_comp.items.get("seed_wheat", 0) > 0
        
        # If no seed, try to get one from stockpile or ground
        if not has_seed:
            # Look for seed in stockpile or on ground
            best_seed_entity = None
            min_seed_dist = float('inf')
            
            for seed_entity, item_comp, seed_pos in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
                if item_comp.item_type == "seed_wheat" and item_comp.amount > 0:
                    seed_zone = self.zone_manager.grid.get_zone(seed_pos.x, seed_pos.y)
                    dist = abs(pos_comp.x - seed_pos.x) + abs(pos_comp.y - seed_pos.y)
                    # Prefer seeds in stockpile
                    if seed_zone == ZONE_STOCKPILE:
                        dist = dist * 0.5
                    if dist < min_seed_dist:
                        min_seed_dist = dist
                        best_seed_entity = seed_entity
            
            if best_seed_entity and min_seed_dist < 30:
                # Go get the seed
                seed_pos = self.entity_manager.get_component(best_seed_entity, PositionComponent)
                dist = abs(pos_comp.x - seed_pos.x) + abs(pos_comp.y - seed_pos.y)
                
                if dist <= 1:  # Adjacent or on the seed
                    action_comp.current_action = "pickup"
                    action_comp.target_entity_id = best_seed_entity
                else:
                    move_comp = self.entity_manager.get_component(entity, MovementComponent)
                    if move_comp:
                        move_comp.target = (seed_pos.x, seed_pos.y)
                        action_comp.current_action = "move"
                        action_comp.target_entity_id = best_seed_entity
                return
            else:
                # No seed available, release job back to pool (don't destroy it)
                Logger.log(LogCategory.AI, f"Entity {entity} can't find seeds for planting job, releasing")
                self.job_system.release_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
                action_comp.current_action = "idle"
                return
        
        # Has seed, proceed to plant
        target_pos = job.target_pos
        dist = abs(pos_comp.x - target_pos[0]) + abs(pos_comp.y - target_pos[1])
        
        if dist <= 1:  # Adjacent or at target
            # At target, plant - complete job now
            action_comp.current_action = "plant"
            self.job_system.complete_job(job.id)
            self.entity_manager.remove_component(entity, JobComponent)
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
        
        # Check if crop is actually ripe (might have changed)
        if job.target_entity_id is not None:
            crop_comp = self.entity_manager.get_component(job.target_entity_id, CropComponent)
            if crop_comp and crop_comp.state != "ripe":
                # Crop not ripe yet, release job
                self.job_system.release_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
                action_comp.current_action = "idle"
                return
        
        target_pos = job.target_pos
        dist = abs(pos_comp.x - target_pos[0]) + abs(pos_comp.y - target_pos[1])
        
        if dist <= 1:
            # Near enough, harvest
            action_comp.current_action = "harvest"
            action_comp.target_entity_id = job.target_entity_id
            # Complete the job now (ActionSystem will do the actual harvesting)
            self.job_system.complete_job(job.id)
            self.entity_manager.remove_component(entity, JobComponent)
        else:
            # Move to target
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp:
                move_comp.target = target_pos
                action_comp.current_action = "move"
    
    def _handle_trap_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        """Handle trap job - check existing trap or place new trap."""
        if job.target_entity_id:
            # Checking existing trap
            trap_entity = job.target_entity_id
            if not self.entity_manager.has_entity(trap_entity):
                # Trap gone, job done
                self.job_system.complete_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
                action_comp.current_action = "idle"
                return
            
            trap_pos = self.entity_manager.get_component(trap_entity, PositionComponent)
            if not trap_pos:
                self.job_system.complete_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
                action_comp.current_action = "idle"
                return
            
            dist = abs(pos_comp.x - trap_pos.x) + abs(pos_comp.y - trap_pos.y)
            if dist <= 1:
                # At trap, check it
                action_comp.current_action = "trap"
                action_comp.target_entity_id = trap_entity
            else:
                # Move to trap
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = (trap_pos.x, trap_pos.y)
                    action_comp.current_action = "move"
        else:
            # Placing new trap
            target_pos = job.target_pos
            dist = abs(pos_comp.x - target_pos[0]) + abs(pos_comp.y - target_pos[1])
            
            if dist <= 1:  # Adjacent or at target
                # At target, place trap
                action_comp.current_action = "trap"
            else:
                # Move to target
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = target_pos
                    action_comp.current_action = "move"
    
    def _handle_fish_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        """Handle fish job - move to water and fish."""
        target_pos = job.target_pos
        dist = abs(pos_comp.x - target_pos[0]) + abs(pos_comp.y - target_pos[1])
        
        # Check if we're at water or adjacent to water
        at_water = False
        if dist <= 1:
            # Check if target is water or we're adjacent to water
            if self.grid.get_terrain(target_pos[0], target_pos[1]) == TERRAIN_WATER:
                at_water = True
            else:
                # Check adjacent tiles for water
                neighbors = [
                    (pos_comp.x+1, pos_comp.y), (pos_comp.x-1, pos_comp.y),
                    (pos_comp.x, pos_comp.y+1), (pos_comp.x, pos_comp.y-1)
                ]
                for nx, ny in neighbors:
                    if 0 <= nx < self.grid.width and 0 <= ny < self.grid.height:
                        if self.grid.get_terrain(nx, ny) == TERRAIN_WATER:
                            at_water = True
                            break
        
        if at_water:
            # At water, start fishing
            action_comp.current_action = "fish"
        else:
            # Move to water
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp:
                move_comp.target = target_pos
                action_comp.current_action = "move"

    def _handle_tend_fire_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        # Already handled placeholder (or logic exists elsewhere)
        pass

    def _handle_haul_to_blueprint_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        inv_comp = self.entity_manager.get_component(entity, InventoryComponent)
        if not inv_comp:
            return
            
        material_type = job.metadata.get("material_type") if job.metadata else None
        if not material_type:
            self.job_system.complete_job(job.id)
            return
            
        has_material = inv_comp.items.get(material_type, 0) > 0

        # If we don't have the material, we need to go to stockpile and pick it up
        if not has_material:
            # Target is stockpile containing the item
            stockpile_pos = None
            stockpile_item_entity = None
            
            # Find item in stockpile
            for item_entity, item_comp, item_pos in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
                if item_comp.item_type == material_type and item_comp.amount > 0:
                    zone = self.grid.get_zone(item_pos.x, item_pos.y)
                    if zone == ZONE_STOCKPILE:
                        stockpile_pos = (item_pos.x, item_pos.y)
                        stockpile_item_entity = item_entity
                        break
                        
            if not stockpile_pos:
                # No material available, release job
                self.job_system.release_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
                action_comp.current_action = "idle"
                self._failed_jobs_cooldown[job.id] = self.time_manager.total_ticks + 120 # Cooldown for 2 seconds
                return
                
            dist_to_stockpile = abs(pos_comp.x - stockpile_pos[0]) + abs(pos_comp.y - stockpile_pos[1])
            if dist_to_stockpile <= 1:
                action_comp.current_action = "pickup"
                action_comp.target_entity_id = stockpile_item_entity
            else:
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = stockpile_pos
                    action_comp.current_action = "move"
        else:
            # We have the material, move to blueprint
            from src.components.building_components import BlueprintComponent
            blueprint = self.entity_manager.get_component(job.target_entity_id, BlueprintComponent)
            
            if not blueprint:
                # Blueprint gone, drop item or go idle
                self.job_system.complete_job(job.id)
                self.entity_manager.remove_component(entity, JobComponent)
                action_comp.current_action = "idle"
                return
                
            # Move to blueprint
            dist_to_blueprint = abs(pos_comp.x - job.target_pos[0]) + abs(pos_comp.y - job.target_pos[1])
            if dist_to_blueprint <= 1:
                # Arrived, drop material into blueprint
                action_comp.current_action = "build_drop"
                action_comp.target_entity_id = job.target_entity_id
                
                # NOTE: The actual transferring of items happens in ActionSystem.
                # Here we just set the action state.
                # Once item is placed, Job is completed in ActionSystem.
            else:
                move_comp = self.entity_manager.get_component(entity, MovementComponent)
                if move_comp:
                    move_comp.target = job.target_pos
                    action_comp.current_action = "move"
                    
    def _handle_build_job(self, entity: int, job: Job, action_comp: ActionComponent, pos_comp: PositionComponent):
        from src.components.building_components import BlueprintComponent
        blueprint = self.entity_manager.get_component(job.target_entity_id, BlueprintComponent)
            
        if not blueprint:
            self.job_system.complete_job(job.id)
            self.entity_manager.remove_component(entity, JobComponent)
            action_comp.current_action = "idle"
            return
            
        dist = abs(pos_comp.x - job.target_pos[0]) + abs(pos_comp.y - job.target_pos[1])
        if dist <= 1:
            action_comp.current_action = "build"
            action_comp.target_entity_id = job.target_entity_id
        else:
            move_comp = self.entity_manager.get_component(entity, MovementComponent)
            if move_comp:
                move_comp.target = job.target_pos
                action_comp.current_action = "move"

