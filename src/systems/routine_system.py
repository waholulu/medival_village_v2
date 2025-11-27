from src.core.ecs import System, EntityManager
from src.components.data_components import RoutineComponent, ActionComponent, HungerComponent, TirednessComponent
from src.core.time_manager import TimeManager
from src.core.config_manager import ConfigManager
from typing import Optional

class RoutineSystem(System):
    """Manages daily routine schedules for villagers."""
    
    def __init__(self, entity_manager: EntityManager, time_manager: TimeManager, config_manager: ConfigManager):
        self.entity_manager = entity_manager
        self.time_manager = time_manager
        self.config_manager = config_manager

    def update(self, dt: float):
        """Update routine system - check schedules and suggest activities."""
        current_hour = self.time_manager.time_of_day
        current_season = self.time_manager.get_season()
        
        # Get schedule config
        schedule_config = self.config_manager.get("entities.villager.daily_schedule", {})
        wake_up = schedule_config.get("wake_up", 6.0)
        breakfast = schedule_config.get("breakfast", [6.0, 8.0])
        work_morning = schedule_config.get("work_morning", [8.0, 12.0])
        lunch = schedule_config.get("lunch", [12.0, 13.0])
        work_afternoon = schedule_config.get("work_afternoon", [13.0, 18.0])
        dinner = schedule_config.get("dinner", [18.0, 19.0])
        leisure = schedule_config.get("leisure", [19.0, 22.0])
        sleep_time = schedule_config.get("sleep", [22.0, 6.0])
        
        # Adjust schedule based on season
        if current_season == "winter":
            # Winter: shorter work hours, earlier sleep
            work_afternoon = [work_afternoon[0], work_afternoon[1] - 2.0]  # End work 2 hours earlier
            sleep_time = [sleep_time[0] - 1.0, sleep_time[1]]  # Sleep 1 hour earlier
        elif current_season == "summer":
            # Summer: midday rest
            midday_rest = [12.0, 14.0]
            if midday_rest[0] <= current_hour < midday_rest[1]:
                # Suggest rest during midday
                pass
        
        for entity, routine_comp, action_comp in self.entity_manager.get_entities_with(
            RoutineComponent, ActionComponent
        ):
            # Check urgent needs first (these override schedule)
            hunger_comp = self.entity_manager.get_component(entity, HungerComponent)
            tiredness_comp = self.entity_manager.get_component(entity, TirednessComponent)
            
            if hunger_comp and hunger_comp.hunger > 80.0:
                # Urgent hunger - should eat (handled by AISystem)
                continue
            
            if tiredness_comp and tiredness_comp.tiredness > 90.0:
                # Urgent tiredness - should sleep (handled by AISystem)
                continue
            
            # Determine current activity based on schedule
            suggested_activity = self._get_suggested_activity(
                current_hour, wake_up, breakfast, work_morning, lunch, 
                work_afternoon, dinner, leisure, sleep_time
            )
            
            routine_comp.current_state = suggested_activity
            routine_comp.next_scheduled_activity = self._get_next_activity(
                current_hour, wake_up, breakfast, work_morning, lunch,
                work_afternoon, dinner, leisure, sleep_time
            )
    
    def _get_suggested_activity(self, hour: float, wake_up: float, breakfast: list, 
                                work_morning: list, lunch: list, work_afternoon: list,
                                dinner: list, leisure: list, sleep_time: list) -> str:
        """Get suggested activity based on current time."""
        # Handle sleep time (can span midnight)
        if sleep_time[0] > sleep_time[1]:  # e.g., [22.0, 6.0]
            if hour >= sleep_time[0] or hour < sleep_time[1]:
                return "SLEEPING"
        else:
            if sleep_time[0] <= hour < sleep_time[1]:
                return "SLEEPING"
        
        # Check other time slots
        if self._in_time_range(hour, breakfast):
            return "EATING"
        elif self._in_time_range(hour, lunch):
            return "EATING"
        elif self._in_time_range(hour, dinner):
            return "EATING"
        elif self._in_time_range(hour, work_morning) or self._in_time_range(hour, work_afternoon):
            return "WORKING"
        elif self._in_time_range(hour, leisure):
            return "SOCIALIZING"
        else:
            return "WORKING"  # Default to working
    
    def _get_next_activity(self, hour: float, wake_up: float, breakfast: list,
                           work_morning: list, lunch: list, work_afternoon: list,
                           dinner: list, leisure: list, sleep_time: list) -> Optional[str]:
        """Get next scheduled activity."""
        # Simple implementation: return next major activity
        if hour < breakfast[0]:
            return "EATING"  # Breakfast
        elif hour < work_morning[0]:
            return "WORKING"  # Work
        elif hour < lunch[0]:
            return "EATING"  # Lunch
        elif hour < work_afternoon[1]:
            return "WORKING"  # Work
        elif hour < dinner[0]:
            return "EATING"  # Dinner
        elif hour < sleep_time[0]:
            return "SOCIALIZING"  # Leisure
        else:
            return "SLEEPING"  # Sleep
    
    def _in_time_range(self, hour: float, time_range: list) -> bool:
        """Check if hour is within time range."""
        if len(time_range) < 2:
            return False
        return time_range[0] <= hour < time_range[1]
    
    def should_eat(self, entity: int) -> bool:
        """Check if entity should eat based on schedule."""
        routine_comp = self.entity_manager.get_component(entity, RoutineComponent)
        if not routine_comp:
            return False
        return routine_comp.current_state == "EATING"
    
    def should_sleep(self, entity: int) -> bool:
        """Check if entity should sleep based on schedule."""
        routine_comp = self.entity_manager.get_component(entity, RoutineComponent)
        if not routine_comp:
            return False
        return routine_comp.current_state == "SLEEPING"
    
    def should_work(self, entity: int) -> bool:
        """Check if entity should work based on schedule."""
        routine_comp = self.entity_manager.get_component(entity, RoutineComponent)
        if not routine_comp:
            return False
        return routine_comp.current_state == "WORKING"

