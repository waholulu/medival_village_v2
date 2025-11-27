from typing import Optional, Tuple
from src.core.ecs import System, EntityManager
from src.components.data_components import ActionComponent, PositionComponent, JobComponent, InventoryComponent, ResourceComponent, ItemComponent
from src.components.skill_component import SkillComponent
from src.systems.job_system import JobSystem, Job
from src.world.grid import Grid, ZONE_STOCKPILE
from src.world.zone_manager import ZoneManager
from src.utils.logger import Logger, LogCategory

class AISystem(System):
    def __init__(self, entity_manager: EntityManager, job_system: JobSystem, grid: Grid, zone_manager: ZoneManager):
        self.entity_manager = entity_manager
        self.job_system = job_system
        self.grid = grid
        self.zone_manager = zone_manager

    def update(self, dt: float):
        # 0. Generate jobs from world state
        self._generate_jobs()

        # 1. Handle entities with jobs
        for entity, job_comp, action_comp, pos_comp in self.entity_manager.get_entities_with(JobComponent, ActionComponent, PositionComponent):
            self._process_job(entity, job_comp, action_comp, pos_comp)

        # 2. Handle idle entities (find jobs)
        for entity, action_comp, skill_comp, pos_comp in self.entity_manager.get_entities_with(ActionComponent, SkillComponent, PositionComponent):
            # Only look for job if no job and idle
            if not self.entity_manager.has_component(entity, JobComponent) and action_comp.current_action == "idle":
                self._find_job(entity, skill_comp, pos_comp)

    def _generate_jobs(self):
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

