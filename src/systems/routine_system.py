from src.core.ecs import System, EntityManager
from src.components.data_components import RoutineComponent, ActionComponent, HungerComponent, TirednessComponent
from src.core.time_manager import TimeManager
from src.core.config_manager import ConfigManager
from typing import Optional, List

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
        season_config = self.config_manager.get(f"time.seasons.{current_season}", {})
        wake_up = schedule_config.get("wake_up", 6.0)
        breakfast = schedule_config.get("breakfast", [6.0, 8.0])
        work_morning = schedule_config.get("work_morning", [8.0, 12.0])
        lunch = schedule_config.get("lunch", [12.0, 13.0])
        work_afternoon = schedule_config.get("work_afternoon", [13.0, 18.0])
        dinner = schedule_config.get("dinner", [18.0, 19.0])
        leisure = schedule_config.get("leisure", [19.0, 22.0])
        sleep_time = schedule_config.get("sleep", [22.0, 6.0])
        rest_ranges = []
        midday_rest = season_config.get("midday_rest_hours")
        if isinstance(midday_rest, list) and len(midday_rest) == 2:
            rest_ranges.append(midday_rest)
        
        # Adjust schedule based on season
        if current_season == "winter":
            # Winter: shorter work hours, earlier sleep
            adjusted_end = max(work_afternoon[0], work_afternoon[1] - 2.0)
            work_afternoon = [work_afternoon[0], adjusted_end]
            sleep_start = (sleep_time[0] - 1.0) % 24.0
            sleep_time = [sleep_start, sleep_time[1]]
        
        for entity, routine_comp, action_comp in self.entity_manager.get_entities_with(
            RoutineComponent, ActionComponent
        ):
            # Always update routine state based on schedule (AI handles urgent overrides)
            # Determine current activity based on schedule
            suggested_activity = self._get_suggested_activity(
                current_hour, wake_up, breakfast, work_morning, lunch, 
                work_afternoon, dinner, leisure, sleep_time, rest_ranges
            )
            
            routine_comp.current_state = suggested_activity
            routine_comp.next_scheduled_activity = self._get_next_activity(
                current_hour, wake_up, breakfast, work_morning, lunch,
                work_afternoon, dinner, leisure, sleep_time
            )
    
    def _get_suggested_activity(self, hour: float, wake_up: float, breakfast: list, 
                                work_morning: list, lunch: list, work_afternoon: list,
                                dinner: list, leisure: list, sleep_time: list,
                                rest_ranges: Optional[List[list[float]]] = None) -> str:
        """Get suggested activity based on current time."""
        # Handle sleep time (can span midnight)
        if sleep_time[0] > sleep_time[1]:  # e.g., [22.0, 6.0]
            if hour >= sleep_time[0] or hour < sleep_time[1]:
                return "SLEEPING"
        else:
            if sleep_time[0] <= hour < sleep_time[1]:
                return "SLEEPING"
        
        # Check meal times
        if self._in_time_range(hour, breakfast):
            return "EATING"
        if self._in_time_range(hour, lunch):
            return "EATING"
        if self._in_time_range(hour, dinner):
            return "EATING"
        
        # Check seasonal rest periods (e.g. midday rest in summer)
        if rest_ranges:
            for rest_range in rest_ranges:
                if self._in_time_range(hour, rest_range):
                    return "RESTING"
        
        # Check work hours
        if self._in_time_range(hour, work_morning) or self._in_time_range(hour, work_afternoon):
            return "WORKING"
        
        # Check leisure time
        if self._in_time_range(hour, leisure):
            return "SOCIALIZING"
        
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
        """Check if hour is within time range. Supports overnight ranges (e.g. [22.0, 6.0])."""
        if len(time_range) < 2:
            return False
        start, end = time_range[0], time_range[1]
        if start <= end:
            # Normal range (e.g. [8.0, 12.0])
            return start <= hour < end
        else:
            # Overnight range (e.g. [22.0, 6.0])
            return hour >= start or hour < end
    
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

