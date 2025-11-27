import pygame
import math
from src.core.ecs import System, EntityManager
from src.components.data_components import PositionComponent, MovementComponent
from src.components.tags import IsTree, IsPlayer
from src.world.grid import Grid, TERRAIN_GRASS, TERRAIN_DIRT, TERRAIN_WATER, TERRAIN_STONE
from src.utils.logger import Logger, LogCategory

# Color definitions
COLOR_GRASS = (34, 139, 34)
COLOR_DIRT = (139, 69, 19)
COLOR_WATER = (65, 105, 225)
COLOR_STONE = (128, 128, 128)
COLOR_UNKNOWN = (255, 0, 255)
COLOR_GRID_LINE = (50, 50, 50)
COLOR_SELECTION = (255, 255, 0)
COLOR_PATH = (200, 200, 0)
COLOR_ENTITY_PLAYER = (0, 0, 255)
COLOR_ENTITY_TREE = (0, 100, 0)
COLOR_ENTITY_DEFAULT = (255, 0, 0)

class RenderSystem(System):
    def __init__(self, screen: pygame.Surface, grid: Grid, entity_manager: EntityManager, config: dict):
        self.screen = screen
        self.grid = grid
        self.entity_manager = entity_manager
        self.base_pixels_per_unit = config.get("global", {}).get("pixels_per_unit", 32)
        
        # Camera Settings
        self.camera_pos = [0.0, 0.0] # World coordinates (top-left of the view)
        self.zoom_level = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 3.0
        
        # Selection
        self.selected_tile = None # (x, y)
        self.selected_entity_id = None
        
        # Pre-calculate colors for faster lookup
        self.terrain_colors = {
            TERRAIN_GRASS: COLOR_GRASS,
            TERRAIN_DIRT: COLOR_DIRT,
            TERRAIN_WATER: COLOR_WATER,
            TERRAIN_STONE: COLOR_STONE
        }
        
        Logger.info("RenderSystem initialized")

    def move_camera(self, dx: float, dy: float):
        speed = 500.0 / self.zoom_level # Adjust speed by zoom so it feels consistent
        self.camera_pos[0] += dx * speed
        self.camera_pos[1] += dy * speed
        
        # Clamp camera to world bounds (optional, but good for safety)
        # max_x = self.grid.width * self.base_pixels_per_unit
        # max_y = self.grid.height * self.base_pixels_per_unit
        # self.camera_pos[0] = max(0, min(self.camera_pos[0], max_x - self.screen.get_width() / self.zoom_level))
        # self.camera_pos[1] = max(0, min(self.camera_pos[1], max_y - self.screen.get_height() / self.zoom_level))

    def adjust_zoom(self, amount: float):
        old_zoom = self.zoom_level
        self.zoom_level += amount * 0.1
        self.zoom_level = max(self.min_zoom, min(self.zoom_level, self.max_zoom))
        
        # Optional: Zoom towards center of screen (math is a bit more complex, skip for now)
        
    def world_to_screen(self, world_x: float, world_y: float) -> tuple[int, int]:
        screen_x = (world_x - self.camera_pos[0]) * self.zoom_level
        screen_y = (world_y - self.camera_pos[1]) * self.zoom_level
        return int(screen_x), int(screen_y)

    def screen_to_world(self, screen_x: int, screen_y: int) -> tuple[float, float]:
        world_x = (screen_x / self.zoom_level) + self.camera_pos[0]
        world_y = (screen_y / self.zoom_level) + self.camera_pos[1]
        return world_x, world_y
    
    def get_tile_at_screen_pos(self, screen_x: int, screen_y: int) -> tuple[int, int]:
        wx, wy = self.screen_to_world(screen_x, screen_y)
        tile_x = int(wx / self.base_pixels_per_unit)
        tile_y = int(wy / self.base_pixels_per_unit)
        return tile_x, tile_y

    def update(self, dt: float):
        # 1. Clear Screen
        self.screen.fill((0, 0, 0))
        
        # 2. Calculate Visible Grid Bounds (Culling)
        ppu = self.base_pixels_per_unit * self.zoom_level
        
        start_col = int(self.camera_pos[0] / self.base_pixels_per_unit)
        start_row = int(self.camera_pos[1] / self.base_pixels_per_unit)
        
        cols_to_draw = int(self.screen.get_width() / ppu) + 2
        rows_to_draw = int(self.screen.get_height() / ppu) + 2
        
        end_col = start_col + cols_to_draw
        end_row = start_row + rows_to_draw
        
        # Clamp to grid size
        start_col = max(0, start_col)
        start_row = max(0, start_row)
        end_col = min(self.grid.width, end_col)
        end_row = min(self.grid.height, end_row)
        
        # 3. Draw Grid
        for x in range(start_col, end_col):
            for y in range(start_row, end_row):
                # Calculate screen position
                # world_pos = x * base_ppu, y * base_ppu
                world_x = x * self.base_pixels_per_unit
                world_y = y * self.base_pixels_per_unit
                
                screen_x, screen_y = self.world_to_screen(world_x, world_y)
                
                # Draw Rectangle
                # Avoid sub-pixel issues with ceil/int if needed, but int is usually fine for rect
                size = math.ceil(ppu)
                rect = (screen_x, screen_y, size, size)
                
                terrain_id = self.grid.get_terrain(x, y)
                color = self.terrain_colors.get(terrain_id, COLOR_UNKNOWN)
                
                pygame.draw.rect(self.screen, color, rect)
                # Only draw grid lines if zoom is high enough, otherwise it looks messy
                if self.zoom_level > 0.6:
                    pygame.draw.rect(self.screen, COLOR_GRID_LINE, rect, 1)
        
        # 4. Draw Entities
        # For better performance, spatial partitioning should be used.
        # Here we iterate all entities with PositionComponent.
        for entity, pos_comp in self.entity_manager.get_entities_with(PositionComponent):
             # Simple culling check
             if not (start_col <= pos_comp.x < end_col and start_row <= pos_comp.y < end_row):
                 continue

             # Determine Color based on Tags
             color = COLOR_ENTITY_DEFAULT
             if self.entity_manager.has_component(entity, IsPlayer):
                 color = COLOR_ENTITY_PLAYER
             elif self.entity_manager.has_component(entity, IsTree):
                 color = COLOR_ENTITY_TREE
             
             world_x = pos_comp.x * self.base_pixels_per_unit
             world_y = pos_comp.y * self.base_pixels_per_unit
             
             # Add smooth movement offset if available
             move_comp = self.entity_manager.get_component(entity, MovementComponent)
             if move_comp and move_comp.path:
                 # Calculate offset based on progress towards next tile
                 # next tile is move_comp.path[0]
                 # current tile is pos_comp.x, pos_comp.y
                 next_x, next_y = move_comp.path[0]
                 dx = next_x - pos_comp.x
                 dy = next_y - pos_comp.y
                 
                 offset_x = dx * move_comp.progress * self.base_pixels_per_unit
                 offset_y = dy * move_comp.progress * self.base_pixels_per_unit
                 
                 world_x += offset_x
                 world_y += offset_y

             screen_x, screen_y = self.world_to_screen(world_x, world_y)
             size = math.ceil(ppu * 0.8) # Slightly smaller than tile
             offset = (math.ceil(ppu) - size) // 2
             
             rect = (screen_x + offset, screen_y + offset, size, size)
             pygame.draw.rect(self.screen, color, rect)
             
             # Highlight if selected
             if entity == self.selected_entity_id:
                 pygame.draw.rect(self.screen, COLOR_SELECTION, rect, 2)
                 
                 # Draw Path
                 if move_comp and move_comp.path:
                     # Draw line from center of entity to center of next tile, etc.
                     center_x = screen_x + offset + size // 2
                     center_y = screen_y + offset + size // 2
                     
                     points = [(center_x, center_y)]
                     
                     # We need to map path nodes to screen coords relative to camera
                     # Path nodes are absolute grid coords
                     
                     # Next tile (the one we are moving to)
                     # We already calculated world_x/y for the entity which includes interpolation
                     # But path nodes are static
                     
                     for px, py in move_comp.path:
                         p_wx = px * self.base_pixels_per_unit + self.base_pixels_per_unit / 2
                         p_wy = py * self.base_pixels_per_unit + self.base_pixels_per_unit / 2
                         p_sx, p_sy = self.world_to_screen(p_wx, p_wy)
                         points.append((p_sx, p_sy))
                     
                     if len(points) > 1:
                         pygame.draw.lines(self.screen, COLOR_PATH, False, points, 2)

        # 5. Draw Selection Box (Tile Selection)
        if self.selected_tile:
            sx, sy = self.selected_tile
            if start_col <= sx < end_col and start_row <= sy < end_row:
                 world_x = sx * self.base_pixels_per_unit
                 world_y = sy * self.base_pixels_per_unit
                 screen_x, screen_y = self.world_to_screen(world_x, world_y)
                 size = math.ceil(ppu)
                 pygame.draw.rect(self.screen, COLOR_SELECTION, (screen_x, screen_y, size, size), 1)


