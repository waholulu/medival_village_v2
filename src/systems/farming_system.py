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
        # Scan farm zone for empty tiles
        # For simplicity, we'll check a few farm tiles (in a real system, we'd cache these)
        # For now, we'll just check if there are any farm zones and create jobs for them
        
        # This is a simplified version - in production, we'd maintain a list of farm tiles
        # and check which ones don't have crops
        
        # For now, we'll skip automatic plant job generation
        # Instead, we'll let the player or other systems create plant jobs manually
        pass

    def _generate_harvest_jobs(self):
        """Generate harvest jobs for ripe crops."""
        for entity, crop_comp, pos_comp in self.entity_manager.get_entities_with(CropComponent, PositionComponent):
            if crop_comp.state != "ripe":
                continue
            
            # Check if already has a job
            has_job = False
            for job in self.job_system.jobs:
                if job.target_entity_id == entity and job.job_type == "harvest":
                    has_job = True
                    break
            
            if has_job:
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

