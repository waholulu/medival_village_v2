from src.core.ecs import System, EntityManager
from src.components.data_components import ColdComponent, FireComponent, PositionComponent, ActionComponent
from src.core.time_manager import TimeManager
from src.core.config_manager import ConfigManager
from src.utils.logger import Logger, LogCategory
import random

class SurvivalSystem(System):
    def __init__(self, entity_manager: EntityManager, time_manager: TimeManager, config_manager: ConfigManager, grid):
        self.entity_manager = entity_manager
        self.time_manager = time_manager
        self.config_manager = config_manager
        self.grid = grid
        
        # Get config values
        self.day_length_seconds = config_manager.get("simulation.day_length_seconds", 10.0)
        self.cold_gain_per_hour_day = config_manager.get("entities.villager.needs.cold_gain_per_hour_day", 1.0)
        self.cold_gain_per_hour_night = config_manager.get("entities.villager.needs.cold_gain_per_hour_night", 5.0)
        self.cold_damage_probability_base = config_manager.get("entities.villager.needs.cold_damage_probability_base", 0.1)
        self.cold_damage_amount = config_manager.get("entities.villager.needs.cold_damage_amount", 2.0)
        
        # Day/night config
        day_night_config = config_manager.get("time.day_night", {})
        self.day_start_hour = day_night_config.get("day_start_hour", 6.0)
        self.day_end_hour = day_night_config.get("day_end_hour", 20.0)

    def update(self, dt: float):
        # 1. Update fire fuel consumption
        self._update_fires(dt)
        
        # 2. Update cold levels for all entities
        self._update_cold(dt)
        
        # 3. Apply cold damage
        self._apply_cold_damage(dt)

    def _update_fires(self, dt: float):
        """Update fire fuel consumption and remove fires that run out of fuel."""
        hours_per_second = 24.0 / self.day_length_seconds
        hours_passed = dt * hours_per_second
        
        for fire_entity, fire_comp, fire_pos in self.entity_manager.get_entities_with(FireComponent, PositionComponent):
            # Consume fuel
            fuel_consumed = fire_comp.fuel_consumption_per_hour * hours_passed
            fire_comp.fuel_remaining -= fuel_consumed
            
            if fire_comp.fuel_remaining <= 0:
                # Fire extinguished
                Logger.log(LogCategory.GAMEPLAY, f"Fire at ({fire_pos.x}, {fire_pos.y}) ran out of fuel")
                self.entity_manager.destroy_entity(fire_entity)

    def _update_cold(self, dt: float):
        """Update cold levels for all entities based on time, season, and proximity to fire."""
        current_season = self.time_manager.get_season()
        season_config = self.config_manager.get(f"time.seasons.{current_season}", {})
        cold_gain_multiplier = season_config.get("cold_gain_multiplier", 1.0)
        
        hours_per_second = 24.0 / self.day_length_seconds
        hours_passed = dt * hours_per_second
        
        is_night = self.time_manager.is_nighttime(self.day_start_hour, self.day_end_hour)
        
        # Get all fire positions for proximity check
        fire_positions = []
        for fire_entity, fire_comp, fire_pos in self.entity_manager.get_entities_with(FireComponent, PositionComponent):
            fire_positions.append((fire_pos.x, fire_pos.y, fire_comp.warmth_radius))
        
        # Update cold for all entities
        for entity, cold_comp, pos_comp in self.entity_manager.get_entities_with(ColdComponent, PositionComponent):
            # Check if near fire
            near_fire = False
            for fx, fy, radius in fire_positions:
                dist = abs(pos_comp.x - fx) + abs(pos_comp.y - fy)
                if dist <= radius:
                    near_fire = True
                    break
            
            if near_fire:
                # Reduce cold near fire
                fire_cold_reduction = self.config_manager.get("entities.fire.fire_cold_reduction_per_hour", 10.0)
                cold_reduction = fire_cold_reduction * hours_passed
                cold_comp.cold = max(0.0, cold_comp.cold - cold_reduction)
            else:
                # Increase cold
                cold_gain_rate = self.cold_gain_per_hour_night if is_night else self.cold_gain_per_hour_day
                cold_gain = cold_gain_rate * hours_passed * cold_gain_multiplier
                cold_comp.cold = min(100.0, cold_comp.cold + cold_gain)

    def _apply_cold_damage(self, dt: float):
        """Apply cold damage to entities with high cold levels."""
        current_season = self.time_manager.get_season()
        season_config = self.config_manager.get(f"time.seasons.{current_season}", {})
        damage_multiplier = season_config.get("cold_damage_probability_multiplier", 1.0)
        
        is_night = self.time_manager.is_nighttime(self.day_start_hour, self.day_end_hour)
        
        hours_per_second = 24.0 / self.day_length_seconds
        hours_passed = dt * hours_per_second
        
        for entity, cold_comp, pos_comp in self.entity_manager.get_entities_with(ColdComponent, PositionComponent):
            if cold_comp.cold > 50.0:  # Only damage if cold is high
                # Check if near fire (no damage if near fire)
                near_fire = False
                for fire_entity, fire_comp, fire_pos in self.entity_manager.get_entities_with(FireComponent, PositionComponent):
                    dist = abs(pos_comp.x - fire_pos.x) + abs(pos_comp.y - fire_pos.y)
                    if dist <= fire_comp.warmth_radius:
                        near_fire = True
                        break
                
                if not near_fire and is_night:
                    # Chance of cold damage
                    damage_prob = self.cold_damage_probability_base * damage_multiplier * hours_passed
                    if random.random() < damage_prob:
                        # Apply damage (we'd need a HealthComponent for this, simplified for now)
                        Logger.log(LogCategory.GAMEPLAY, f"Entity {entity} took {self.cold_damage_amount} cold damage (cold: {cold_comp.cold:.1f})")
                        # In a full system, we'd reduce health here

