from src.core.ecs import System, EntityManager
from src.components.data_components import CropComponent, PositionComponent, ItemComponent
from src.systems.job_system import JobSystem, Job
from src.world.grid import Grid, ZONE_FARM
from src.world.zone_manager import ZoneManager
from src.core.time_manager import TimeManager
from src.core.config_manager import ConfigManager
from src.utils.logger import Logger, LogCategory

class FarmingSystem(System):
    def __init__(self, entity_manager: EntityManager, job_system: JobSystem, grid: Grid, 
                 zone_manager: ZoneManager, time_manager: TimeManager, config_manager: ConfigManager):
        self.entity_manager = entity_manager
        self.job_system = job_system
        self.grid = grid
        self.zone_manager = zone_manager
        self.time_manager = time_manager
        self.config_manager = config_manager

    def update(self, dt: float):
        # 1. Update crop growth
        self._update_crop_growth(dt)
        
        # 2. Generate plant jobs (for empty farm tiles)
        self._generate_plant_jobs()
        
        # 3. Generate harvest jobs (for ripe crops)
        self._generate_harvest_jobs()

    def _update_crop_growth(self, dt: float):
        """Update growth progress of all crops based on time and season."""
        current_season = self.time_manager.get_season()
        season_config = self.config_manager.get(f"time.seasons.{current_season}", {})
        crop_growth_multiplier = season_config.get("crop_growth_multiplier", 1.0)
        
        day_length = self.config_manager.get("simulation.day_length_seconds", 600.0)
        hours_per_second = 24.0 / day_length
        hours_passed = dt * hours_per_second
        
        for entity, crop_comp, pos_comp in self.entity_manager.get_entities_with(CropComponent, PositionComponent):
            if crop_comp.state == "seed":
                crop_comp.state = "growing"
            
            if crop_comp.state == "growing":
                # Get crop config
                crop_config = self.config_manager.get(f"entities.crops.{crop_comp.crop_type}", {})
                growth_days = crop_config.get("growth_days", 3.0)
                
                # Calculate growth progress
                days_passed = hours_passed / 24.0
                growth_rate = (1.0 / growth_days) * crop_growth_multiplier
                crop_comp.growth_progress += growth_rate * days_passed
                
                if crop_comp.growth_progress >= 1.0:
                    crop_comp.growth_progress = 1.0
                    crop_comp.state = "ripe"
                    Logger.log(LogCategory.GAMEPLAY, f"Crop {entity} ({crop_comp.crop_type}) is now ripe!")

    def _generate_plant_jobs(self):
        """Generate plant jobs for empty farm tiles that need crops."""
        # Only generate plant jobs occasionally to avoid spam
        current_tick = self.time_manager.total_ticks if self.time_manager else 0
        if not hasattr(self, '_last_plant_job_tick'):
            self._last_plant_job_tick = 0
        
        # Generate jobs every 20 ticks
        if current_tick - self._last_plant_job_tick < 20:
            return
        self._last_plant_job_tick = current_tick
        
        # Count total available seeds (on ground / in stockpile)
        total_seeds = 0
        for entity, item_comp, pos_comp in self.entity_manager.get_entities_with(ItemComponent, PositionComponent):
            if item_comp.item_type == "seed_wheat" and item_comp.amount > 0:
                total_seeds += item_comp.amount
        
        if total_seeds <= 0:
            # No seeds available, can't plant
            return
        
        # Get farm zone tiles from zone_manager cache
        if ZONE_FARM not in self.zone_manager.zone_cache:
            return
        
        # Limit number of plant jobs to available seeds and max cap
        existing_plant_jobs = sum(1 for job in self.job_system.jobs if job.job_type == "plant")
        max_plant_jobs = min(5, total_seeds)  # Don't create more jobs than seeds
        
        if existing_plant_jobs >= max_plant_jobs:
            return
        
        # Find empty farm tiles (tiles without crops)
        farm_tiles = list(self.zone_manager.zone_cache[ZONE_FARM])
        
        # Get all crop positions
        crop_positions = set()
        for crop_entity, crop_comp, crop_pos in self.entity_manager.get_entities_with(CropComponent, PositionComponent):
            crop_positions.add((crop_pos.x, crop_pos.y))
        
        # Find empty farm tiles (no crop and no existing plant job)
        # Collect existing plant job target positions for fast lookup
        plant_job_positions = set()
        for job in self.job_system.jobs:
            if job.job_type == "plant":
                plant_job_positions.add(job.target_pos)
        
        empty_farm_tiles = []
        for fx, fy in farm_tiles:
            if (fx, fy) not in crop_positions and (fx, fy) not in plant_job_positions:
                empty_farm_tiles.append((fx, fy))
        
        # Create plant jobs for empty tiles (limit to max_plant_jobs)
        for fx, fy in empty_farm_tiles[:max_plant_jobs - existing_plant_jobs]:
            self.job_system.add_job(Job(
                job_type="plant",
                target_pos=(fx, fy),
                target_entity_id=None,
                required_skill="farming",
                priority=3  # Medium priority
            ))
            Logger.log(LogCategory.AI, f"Created Plant job for empty farm tile at {fx},{fy}")

    def _generate_harvest_jobs(self):
        """Generate harvest jobs for ripe crops."""
        for entity, crop_comp, pos_comp in self.entity_manager.get_entities_with(CropComponent, PositionComponent):
            if crop_comp.state != "ripe":
                continue
            
            # Check if already has a harvest job (O(1) lookup via index)
            if self.job_system.has_job_for_entity(entity, "harvest"):
                continue
            
            # Create harvest job (high priority)
            self.job_system.add_job(Job(
                job_type="harvest",
                target_pos=(pos_comp.x, pos_comp.y),
                target_entity_id=entity,
                required_skill="farming",
                priority=5  # Higher than other jobs
            ))
            Logger.log(LogCategory.AI, f"Created Harvest job for {crop_comp.crop_type} at {pos_comp.x},{pos_comp.y}")

