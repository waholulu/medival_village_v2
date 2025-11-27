import pygame
from src.core.ecs import System, EntityManager
from src.world.grid import Grid, TERRAIN_GRASS, TERRAIN_DIRT, TERRAIN_WATER, TERRAIN_STONE

# Color definitions
COLOR_GRASS = (34, 139, 34)
COLOR_DIRT = (139, 69, 19)
COLOR_WATER = (65, 105, 225)
COLOR_STONE = (128, 128, 128)
COLOR_UNKNOWN = (255, 0, 255)
COLOR_GRID_LINE = (50, 50, 50)

class RenderSystem(System):
    def __init__(self, screen: pygame.Surface, grid: Grid, entity_manager: EntityManager, config: dict):
        self.screen = screen
        self.grid = grid
        self.entity_manager = entity_manager
        self.pixels_per_unit = config.get("global", {}).get("pixels_per_unit", 32)
        self.font = pygame.font.SysFont("Arial", 16)
        
        # Pre-calculate colors for faster lookup
        self.terrain_colors = {
            TERRAIN_GRASS: COLOR_GRASS,
            TERRAIN_DIRT: COLOR_DIRT,
            TERRAIN_WATER: COLOR_WATER,
            TERRAIN_STONE: COLOR_STONE
        }

    def update(self, dt: float):
        # 1. Clear Screen
        self.screen.fill((0, 0, 0))
        
        # 2. Draw Grid (Optimized: iterate only visible range if we had a camera)
        # For Phase 0, we just draw everything or a small viewport
        # Let's draw the whole grid but clipped to screen size
        rows, cols = self.grid.width, self.grid.height
        
        for x in range(rows):
            for y in range(cols):
                rect = (x * self.pixels_per_unit, y * self.pixels_per_unit, self.pixels_per_unit, self.pixels_per_unit)
                
                # Simple Culling
                if rect[0] > self.screen.get_width() or rect[1] > self.screen.get_height():
                    continue
                    
                terrain_id = self.grid.get_terrain(x, y)
                color = self.terrain_colors.get(terrain_id, COLOR_UNKNOWN)
                
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, COLOR_GRID_LINE, rect, 1) # Grid line

    def draw_debug_info(self, fps: float, tick_rate: int, time_scale: float, paused: bool):
        # Draw FPS and status
        info_text = [
            f"FPS: {fps:.1f}",
            f"Tick Rate: {tick_rate}",
            f"Time Scale: {time_scale:.1f}x",
            f"Status: {'PAUSED' if paused else 'RUNNING'}"
        ]
        
        y_offset = 10
        for line in info_text:
            text_surf = self.font.render(line, True, (255, 255, 255))
            self.screen.blit(text_surf, (10, y_offset))
            y_offset += 20

