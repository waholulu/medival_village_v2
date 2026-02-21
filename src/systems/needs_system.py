from src.core.ecs import System, EntityManager
from src.components.data_components import HungerComponent, TirednessComponent, MoodComponent, ActionComponent, RoutineComponent
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
        self.hunger_work_multiplier = config_manager.get("entities.villager.needs.hunger_work_multiplier", 1.2)
        self.hunger_rest_multiplier = config_manager.get("entities.villager.needs.hunger_rest_multiplier", 0.8)
        self.tiredness_work_multiplier = config_manager.get("entities.villager.needs.tiredness_work_multiplier", 1.0)
        self.tiredness_rest_multiplier = config_manager.get("entities.villager.needs.tiredness_rest_multiplier", 1.0)
        
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
            routine_comp = self.entity_manager.get_component(entity, RoutineComponent)
            schedule_state = routine_comp.current_state if routine_comp else None
            resting_state = schedule_state in {"RESTING", "SLEEPING"}
            working_state = schedule_state == "WORKING"
            action_comp = self.entity_manager.get_component(entity, ActionComponent)
            current_action = action_comp.current_action if action_comp else "idle"
            is_sleeping = current_action == "sleep"
            is_moving = current_action == "move"
            is_hard_working = current_action not in ["idle", "sleep", "eat", "move"]

            # Update hunger (increases over time, affected by season)
            hunger_multiplier = self.food_consumption_multiplier
            if is_hard_working or working_state:
                hunger_multiplier *= self.hunger_work_multiplier
            elif resting_state or is_moving:
                hunger_multiplier *= self.hunger_rest_multiplier
            hunger_increase = self.hunger_per_hour * hours_passed * hunger_multiplier
            hunger_comp.hunger = min(100.0, hunger_comp.hunger + hunger_increase)
            
            # Update tiredness (increases when working, decreases when resting/sleeping)
            # Only actual sleep or idle-in-rest-period grants recovery;
            # walking during a rest period is NOT resting.
            rest_multiplier = None
            if is_sleeping:
                rest_multiplier = self.tiredness_rest_multiplier
            elif resting_state and not is_hard_working and not is_moving:
                rest_multiplier = self.tiredness_rest_multiplier * 0.5
            
            if rest_multiplier is not None:
                tiredness_change = self.tiredness_per_hour_resting * hours_passed * rest_multiplier
                tiredness_comp.tiredness = max(0.0, tiredness_comp.tiredness + tiredness_change)
            elif is_moving:
                # Walking is lighter than hard labour — tiredness grows at 40% rate
                tiredness_multiplier = self.tiredness_work_multiplier * 0.4
                if is_night:
                    tiredness_multiplier *= 1.5
                tiredness_change = self.tiredness_per_hour_working * hours_passed * tiredness_multiplier
                tiredness_comp.tiredness = min(100.0, tiredness_comp.tiredness + tiredness_change)
            elif is_hard_working or working_state:
                # Hard work increases tiredness (more at night)
                tiredness_multiplier = self.tiredness_work_multiplier
                if is_night:
                    tiredness_multiplier *= 1.5
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

