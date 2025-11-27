import time

class TimeManager:
    def __init__(self, tick_rate: int = 60):
        self.tick_rate = tick_rate
        self.target_dt = 1.0 / tick_rate
        
        self.last_time = time.time()
        self.delta_time = 0.0
        self.time_scale = 1.0
        self.is_paused = False
        
        self.elapsed_time = 0.0 # Game world time (scaled)
        self.real_time_elapsed = 0.0 # Real application time
        
        self.frame_count = 0
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
        else:
            self.delta_time = 0.0
            
        # Calculate FPS
        self.frame_count += 1
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

