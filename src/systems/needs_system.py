from src.core.ecs import System, EntityManager
from src.components.data_components import HungerComponent, TirednessComponent, MoodComponent, ActionComponent
from src.core.time_manager import TimeManager
from src.core.config_manager import ConfigManager

class NeedsSystem(System):
    def __init__(self, entity_manager: EntityManager, time_manager: TimeManager, config_manager: ConfigManager):
        self.entity_manager = entity_manager
        self.time_manager = time_manager
        self.config_manager = config_manager
        
        # Get config values
        self.day_length_seconds = config_manager.get("simulation.day_length_seconds", 600.0)
        self.hunger_per_hour = config_manager.get("entities.villager.needs.hunger_per_hour", 2.0)
        self.tiredness_per_hour_working = config_manager.get("entities.villager.needs.tiredness_per_hour_working", 5.0)
        self.tiredness_per_hour_resting = config_manager.get("entities.villager.needs.tiredness_per_hour_resting", -10.0)
        
        # Get season config
        current_season = time_manager.get_season()
        season_config = config_manager.get(f"time.seasons.{current_season}", {})
        self.food_consumption_multiplier = season_config.get("food_consumption_multiplier", 1.0)
        
        # Day/night config
        day_night_config = config_manager.get("time.day_night", {})
        self.day_start_hour = day_night_config.get("day_start_hour", 6.0)
        self.day_end_hour = day_night_config.get("day_end_hour", 20.0)

    def update(self, dt: float):
        # Update season multiplier if season changed
        current_season = self.time_manager.get_season()
        season_config = self.config_manager.get(f"time.seasons.{current_season}", {})
        self.food_consumption_multiplier = season_config.get("food_consumption_multiplier", 1.0)
        
        # Calculate time-based multipliers
        hours_per_second = 24.0 / self.day_length_seconds
        hours_passed = dt * hours_per_second
        
        # Check if it's nighttime
        is_night = self.time_manager.is_nighttime(self.day_start_hour, self.day_end_hour)
        
        # Update all entities with needs components
        for entity, hunger_comp, tiredness_comp, mood_comp in self.entity_manager.get_entities_with(
            HungerComponent, TirednessComponent, MoodComponent
        ):
            # Update hunger (increases over time, affected by season)
            hunger_increase = self.hunger_per_hour * hours_passed * self.food_consumption_multiplier
            hunger_comp.hunger = min(100.0, hunger_comp.hunger + hunger_increase)
            
            # Update tiredness (increases when working, decreases when resting/sleeping)
            action_comp = self.entity_manager.get_component(entity, ActionComponent)
            is_working = action_comp and action_comp.current_action not in ["idle", "sleep", "eat"]
            is_sleeping = action_comp and action_comp.current_action == "sleep"
            
            if is_sleeping:
                # Resting reduces tiredness
                tiredness_change = self.tiredness_per_hour_resting * hours_passed
                tiredness_comp.tiredness = max(0.0, tiredness_comp.tiredness + tiredness_change)
            elif is_working:
                # Working increases tiredness (more at night)
                tiredness_multiplier = 1.5 if is_night else 1.0
                tiredness_change = self.tiredness_per_hour_working * hours_passed * tiredness_multiplier
                tiredness_comp.tiredness = min(100.0, tiredness_comp.tiredness + tiredness_change)
            
            # Update mood (decreases if needs are unmet, slowly recovers otherwise)
            if hunger_comp.hunger > 80.0:
                mood_comp.mood = max(0.0, mood_comp.mood - hours_passed)
            elif tiredness_comp.tiredness > 90.0:
                mood_comp.mood = max(0.0, mood_comp.mood - hours_passed)
            else:
                # Slowly recover mood
                mood_comp.mood = min(100.0, mood_comp.mood + 0.5 * hours_passed)

