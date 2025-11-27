import pygame
import json
import os
from src.core.ecs import EntityManager
from src.core.time_manager import TimeManager
from src.world.grid import Grid, TERRAIN_WATER, TERRAIN_STONE
from src.systems.render_system import RenderSystem

def load_config(path: str = "config/balance.json") -> dict:
    if not os.path.exists(path):
        print(f"Warning: Config file {path} not found. Using defaults.")
        return {}
    with open(path, 'r') as f:
        return json.load(f)

def main():
    # 1. Initialization
    pygame.init()
    
    config = load_config()
    global_conf = config.get("global", {})
    
    width = global_conf.get("screen_width", 1280)
    height = global_conf.get("screen_height", 720)
    title = global_conf.get("title", "Project Medieval")
    tick_rate = global_conf.get("tick_rate", 60)
    
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(title)
    
    # 2. Core Systems Setup
    time_manager = TimeManager(tick_rate=tick_rate)
    entity_manager = EntityManager()
    
    # 3. World Generation (Test Data)
    map_width = width // global_conf.get("pixels_per_unit", 32) + 5
    map_height = height // global_conf.get("pixels_per_unit", 32) + 5
    grid = Grid(map_width, map_height)
    
    # Create some test terrain
    grid.set_terrain(5, 5, TERRAIN_WATER)
    grid.set_terrain(6, 5, TERRAIN_WATER)
    grid.set_terrain(7, 5, TERRAIN_WATER)
    grid.set_terrain(2, 2, TERRAIN_STONE)
    
    # 4. Systems
    render_system = RenderSystem(screen, grid, entity_manager, config)
    
    # 5. Game Loop
    running = True
    clock = pygame.time.Clock()
    
    while running:
        # Input Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    time_manager.toggle_pause()
                elif event.key == pygame.K_1:
                    time_manager.set_time_scale(1.0)
                elif event.key == pygame.K_2:
                    time_manager.set_time_scale(2.0)
                elif event.key == pygame.K_3:
                    time_manager.set_time_scale(5.0)
                elif event.key == pygame.K_ESCAPE:
                    running = False
        
        # Update
        time_manager.update()
        
        # Render
        render_system.update(time_manager.get_delta_time())
        
        # Draw Overlay (Debug Info)
        render_system.draw_debug_info(
            fps=time_manager.fps,
            tick_rate=tick_rate,
            time_scale=time_manager.time_scale,
            paused=time_manager.is_paused
        )
        
        pygame.display.flip()
        
        # Cap framerate
        clock.tick(tick_rate)

    pygame.quit()

if __name__ == "__main__":
    main()

