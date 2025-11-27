import time
from typing import Literal

Season = Literal["spring", "summer", "autumn", "winter"]
DayNightState = Literal["day", "night", "dawn", "dusk"]

class TimeManager:
    def __init__(self, tick_rate: int = 60, day_length_seconds: float = 60.0, 
                 season_length_days: int = 90, starting_season: Season = "spring"):
        self.tick_rate = tick_rate
        self.target_dt = 1.0 / tick_rate
        
        self.last_time = time.time()
        self.delta_time = 0.0
        self.time_scale = 1.0
        self.is_paused = False
        
        self.elapsed_time = 0.0 # Game world time (scaled)
        self.real_time_elapsed = 0.0 # Real application time
        
        # Game World Calendar
        self.day = 0
        self.time_of_day = 6.0 # Start at 6 AM
        self.day_length_seconds = day_length_seconds
        self.season_length_days = season_length_days
        self.current_season: Season = starting_season
        
        self.frame_count = 0 # Frames in the current second (for FPS calc)
        self.total_ticks = 0 # Total ticks since start
        self.last_fps_time = self.last_time
        self.fps = 0.0

    def update(self):
        current_time = time.time()
        raw_dt = current_time - self.last_time
        self.last_time = current_time
        
        # Cap dt to avoid spiral of death if lag occurs (e.g. max 0.1s)
        raw_dt = min(raw_dt, 0.1)
        
        self.real_time_elapsed += raw_dt
        
        if not self.is_paused:
            self.delta_time = raw_dt * self.time_scale
            self.elapsed_time += self.delta_time
            
            # Update Calendar
            # delta_time is in seconds. 
            # Game hours per second = 24 / day_length_seconds
            hours_passed = (self.delta_time / self.day_length_seconds) * 24.0
            self.time_of_day += hours_passed
            
            if self.time_of_day >= 24.0:
                self.time_of_day -= 24.0
                self.day += 1
                # Update season
                self._update_season()
        else:
            self.delta_time = 0.0
            
        # Calculate FPS
        self.frame_count += 1
        self.total_ticks += 1
        
        if current_time - self.last_fps_time >= 1.0:
            self.fps = self.frame_count / (current_time - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = current_time

    def set_time_scale(self, scale: float):
        self.time_scale = max(0.0, scale)
        print(f"Time scale set to: {self.time_scale}x")

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        state = "PAUSED" if self.is_paused else "RESUMED"
        print(f"Game {state}")

    def get_delta_time(self) -> float:
        return self.delta_time
    
    def _update_season(self):
        """Update current season based on day count."""
        season_index = (self.day // self.season_length_days) % 4
        seasons: list[Season] = ["spring", "summer", "autumn", "winter"]
        self.current_season = seasons[season_index]
    
    def get_season(self) -> Season:
        """Get current season."""
        return self.current_season
    
    def get_day_night_state(self, day_start_hour: float = 6.0, day_end_hour: float = 20.0) -> DayNightState:
        """Get current day/night state based on time of day."""
        hour = self.time_of_day
        
        # Dawn: 5:00-7:00
        if 5.0 <= hour < 7.0:
            return "dawn"
        # Dusk: 19:00-21:00
        elif 19.0 <= hour < 21.0:
            return "dusk"
        # Day: 6:00-20:00
        elif day_start_hour <= hour < day_end_hour:
            return "day"
        # Night: 20:00-6:00
        else:
            return "night"
    
    def is_daytime(self, day_start_hour: float = 6.0, day_end_hour: float = 20.0) -> bool:
        """Check if it's currently daytime."""
        hour = self.time_of_day
        return day_start_hour <= hour < day_end_hour
    
    def is_nighttime(self, day_start_hour: float = 6.0, day_end_hour: float = 20.0) -> bool:
        """Check if it's currently nighttime."""
        return not self.is_daytime(day_start_hour, day_end_hour)
