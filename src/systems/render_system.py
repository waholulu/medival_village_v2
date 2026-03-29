import pygame
import math
from src.core.ecs import System, EntityManager
from src.components.data_components import PositionComponent, MovementComponent
from src.components.building_components import BlueprintComponent, BuildingComponent
from src.components.tags import IsTree, IsPlayer, IsVillager
from src.world.grid import Grid, TERRAIN_GRASS, TERRAIN_DIRT, TERRAIN_WATER, TERRAIN_STONE, ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL, ZONE_NONE
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

# Entity colors
COLOR_ENTITY_PLAYER = (240, 190, 150) # Skin tone base
COLOR_ENTITY_SHIRT = (50, 120, 200) # Blue shirt
COLOR_ENTITY_TREE_TRUNK = (100, 60, 30) # Dark brown
COLOR_ENTITY_TREE_LEAVES_1 = (34, 139, 34)  # Green 1
COLOR_ENTITY_TREE_LEAVES_2 = (40, 150, 40)  # Green 2
COLOR_ENTITY_BUILDING_WALL = (210, 190, 160) # Beige wall
COLOR_ENTITY_BUILDING_ROOF = (180, 60, 50) # Red roof
COLOR_ENTITY_BLUEPRINT = (0, 255, 255)  # Cyan
COLOR_ENTITY_DEFAULT = (200, 200, 200)
COLOR_SHADOW = (0, 0, 0, 80) # Semi-transparent black

# Zone colors (semi-transparent overlays) - RGB only, alpha handled separately
COLOR_ZONE_STOCKPILE = (255, 200, 0)  # Orange-yellow
COLOR_ZONE_FARM = (0, 200, 0)  # Green
COLOR_ZONE_RESIDENTIAL = (200, 0, 200)  # Magenta
ZONE_ALPHA = 128  # Transparency level

class RenderSystem(System):
    def __init__(self, screen: pygame.Surface, grid: Grid, entity_manager: EntityManager, config: dict, zone_manager=None, time_manager=None):
        self.screen = screen
        self.grid = grid
        self.entity_manager = entity_manager
        self.zone_manager = zone_manager
        self.time_manager = time_manager
        self.base_pixels_per_unit = config.get("global", {}).get("pixels_per_unit", 32)
        
        # Camera Settings
        self.camera_pos = [0.0, 0.0] # World coordinates (top-left of the view)
        self.zoom_level = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 3.0
        
        # Selection
        self.selected_tile = None # (x, y)
        self.selected_entity_id = None
        
        # Zone visibility
        self.show_zones = True  # Toggle zone overlay
        
        # Pre-calculate colors for faster lookup
        self.terrain_colors = {
            TERRAIN_GRASS: COLOR_GRASS,
            TERRAIN_DIRT: COLOR_DIRT,
            TERRAIN_WATER: COLOR_WATER,
            TERRAIN_STONE: COLOR_STONE
        }
        
        # Zone colors mapping
        self.zone_colors = {
            ZONE_STOCKPILE: COLOR_ZONE_STOCKPILE,
            ZONE_FARM: COLOR_ZONE_FARM,
            ZONE_RESIDENTIAL: COLOR_ZONE_RESIDENTIAL
        }
        
        # Pre-cached zone overlay surfaces (keyed by (zone_id, tile_size))
        self._zone_surface_cache: dict[tuple, pygame.Surface] = {}
        
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
        
        # Invalidate zone surface cache when zoom changes (tile size changes)
        if self.zoom_level != old_zoom:
            self._zone_surface_cache.clear()
        
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
                color = self._get_terrain_color(x, y, terrain_id)
                
                pygame.draw.rect(self.screen, color, rect)
                
                # Draw zone overlay if enabled
                if self.show_zones and self.zone_manager:
                    zone_id = self.grid.get_zone(x, y)
                    if zone_id != ZONE_NONE and zone_id in self.zone_colors:
                        # Use cached surface to avoid per-tile per-frame allocation
                        cache_key = (zone_id, size)
                        zone_surface = self._zone_surface_cache.get(cache_key)
                        if zone_surface is None:
                            zone_color = self.zone_colors[zone_id]
                            zone_surface = pygame.Surface((size, size), pygame.SRCALPHA)
                            zone_surface.fill((*zone_color, ZONE_ALPHA))
                            self._zone_surface_cache[cache_key] = zone_surface
                        self.screen.blit(zone_surface, (screen_x, screen_y))
                
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

             # Draw entity with procedural shapes and animations
             self._draw_entity(entity, pos_comp, start_col, end_col, start_row, end_row, ppu)

        # 5. Draw Selection Box (Tile Selection)
        if self.selected_tile:
            sx, sy = self.selected_tile
            if start_col <= sx < end_col and start_row <= sy < end_row:
                 world_x = sx * self.base_pixels_per_unit
                 world_y = sy * self.base_pixels_per_unit
                 screen_x, screen_y = self.world_to_screen(world_x, world_y)
                 size = math.ceil(ppu)
                 pygame.draw.rect(self.screen, COLOR_SELECTION, (screen_x, screen_y, size, size), 1)
        
        # 6. Draw Seasonal Tint Overlay
        if self.time_manager:
            self._draw_seasonal_tint()
        
        # 7. Draw Day/Night Lighting Mask
        if self.time_manager:
            self._draw_day_night_lighting()
    
    def _get_terrain_color(self, x: int, y: int, terrain_id: int) -> tuple[int, int, int]:
        base_color = self.terrain_colors.get(terrain_id, COLOR_UNKNOWN)
        if base_color == COLOR_UNKNOWN:
            return base_color
            
        r, g, b = base_color
        
        if terrain_id == TERRAIN_WATER:
            if self.time_manager:
                t = self.time_manager.real_time_elapsed
                # simple wave based on coordinates and time
                wave = math.sin(x * 0.5 + y * 0.5 + t * 2.0)
                variation = int(wave * 15)
                r = max(0, min(255, r + variation))
                g = max(0, min(255, g + variation))
                b = max(0, min(255, b + variation + 10)) # Boost blue slightly
        else:
            # Pseudo-random noise for grass, dirt, stone
            noise = (math.sin(x * 12.9898 + y * 78.233) * 43758.5453) % 1.0
            variation = int((noise - 0.5) * 20)
            r = max(0, min(255, r + variation))
            g = max(0, min(255, g + variation))
            b = max(0, min(255, b + variation))
            
        return (r, g, b)

    def _draw_entity(self, entity: int, pos_comp: PositionComponent, start_col: int, end_col: int, start_row: int, end_row: int, ppu: float):
        world_x = pos_comp.x * self.base_pixels_per_unit
        world_y = pos_comp.y * self.base_pixels_per_unit
        
        move_comp = self.entity_manager.get_component(entity, MovementComponent)
        is_moving = False
        if move_comp and move_comp.path:
            is_moving = True
            next_x, next_y = move_comp.path[0]
            dx = next_x - pos_comp.x
            dy = next_y - pos_comp.y
            
            offset_x = dx * move_comp.progress * self.base_pixels_per_unit
            offset_y = dy * move_comp.progress * self.base_pixels_per_unit
            
            world_x += offset_x
            world_y += offset_y
            
        screen_x, screen_y = self.world_to_screen(world_x, world_y)
        tile_size = math.ceil(ppu)
        center_x = screen_x + tile_size // 2
        center_y = screen_y + tile_size // 2
        
        # Determine entity type
        is_player = self.entity_manager.has_component(entity, IsPlayer) or self.entity_manager.has_component(entity, IsVillager)
        is_tree = self.entity_manager.has_component(entity, IsTree)
        is_building = self.entity_manager.has_component(entity, BuildingComponent)
        blueprint_comp = self.entity_manager.get_component(entity, BlueprintComponent)
        is_blueprint = blueprint_comp is not None

        # Draw drop shadow
        if not is_blueprint:
            shadow_w = int(tile_size * 0.7)
            shadow_h = int(tile_size * 0.3)
            shadow_y = center_y + int(tile_size * 0.3)
            # Create a per-frame surface for shadow to support alpha. Can be optimized if slow.
            shadow_surface = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_surface, COLOR_SHADOW, (0, 0, shadow_w, shadow_h))
            self.screen.blit(shadow_surface, (center_x - shadow_w // 2, shadow_y - shadow_h // 2))

        # Base shapes drawing
        if is_player:
            # Movement bobbing
            bobbing_y = 0
            if is_moving and self.time_manager:
                bobbing_y = int(abs(math.sin(move_comp.progress * math.pi * 2)) * tile_size * 0.15)
                
            head_radius = int(tile_size * 0.2)
            body_w = int(tile_size * 0.4)
            body_h = int(tile_size * 0.4)
            
            # Shirt/Body
            body_rect = (center_x - body_w // 2, center_y - bobbing_y, body_w, body_h)
            pygame.draw.rect(self.screen, COLOR_ENTITY_SHIRT, body_rect, border_radius=int(tile_size*0.1))
            
            # Head
            head_center = (center_x, center_y - head_radius - bobbing_y)
            pygame.draw.circle(self.screen, COLOR_ENTITY_PLAYER, head_center, head_radius)
            
        elif is_tree:
            trunk_w = int(tile_size * 0.2)
            trunk_h = int(tile_size * 0.4)
            trunk_rect = (center_x - trunk_w // 2, center_y, trunk_w, trunk_h)
            pygame.draw.rect(self.screen, COLOR_ENTITY_TREE_TRUNK, trunk_rect)
            
            # Crown (3 overlapping circles)
            radius = int(tile_size * 0.35)
            pygame.draw.circle(self.screen, COLOR_ENTITY_TREE_LEAVES_1, (center_x, center_y - int(tile_size * 0.1)), radius)
            pygame.draw.circle(self.screen, COLOR_ENTITY_TREE_LEAVES_2, (center_x - int(tile_size * 0.15), center_y - int(tile_size * 0.3)), int(radius * 0.8))
            pygame.draw.circle(self.screen, COLOR_ENTITY_TREE_LEAVES_1, (center_x + int(tile_size * 0.15), center_y - int(tile_size * 0.3)), int(radius * 0.8))
            
        elif is_building:
            wall_w = int(tile_size * 0.8)
            wall_h = int(tile_size * 0.6)
            wall_rect = (center_x - wall_w // 2, center_y - int(tile_size * 0.1), wall_w, wall_h)
            pygame.draw.rect(self.screen, COLOR_ENTITY_BUILDING_WALL, wall_rect)
            
            # Roof (polygon)
            roof_points = [
                (center_x - wall_w // 2 - int(tile_size * 0.1), center_y - int(tile_size * 0.1)),
                (center_x + wall_w // 2 + int(tile_size * 0.1), center_y - int(tile_size * 0.1)),
                (center_x, center_y - int(tile_size * 0.6))
            ]
            pygame.draw.polygon(self.screen, COLOR_ENTITY_BUILDING_ROOF, roof_points)
            
        elif is_blueprint:
            # Blueprint breathing effect
            alpha = 255
            if self.time_manager:
                alpha = int(155 + 100 * math.sin(self.time_manager.real_time_elapsed * 3.0))
            
            bp_surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            bp_color = (*COLOR_ENTITY_BLUEPRINT, alpha)
            bp_rect = (int(tile_size*0.1), int(tile_size*0.1), int(tile_size*0.8), int(tile_size*0.8))
            pygame.draw.rect(bp_surface, bp_color, bp_rect, 3, border_radius=4)
            
            # Progress fill
            if blueprint_comp.work_required > 0:
                progress = blueprint_comp.work_completed / blueprint_comp.work_required
                if progress > 0:
                    inner_h = int(tile_size * 0.8 * progress)
                    inner_rect = (int(tile_size*0.1), int(tile_size*0.9) - inner_h, int(tile_size*0.8), inner_h)
                    pygame.draw.rect(bp_surface, (*COLOR_ENTITY_BLUEPRINT, int(alpha * 0.5)), inner_rect, border_radius=2)
                    
            self.screen.blit(bp_surface, (screen_x, screen_y))
            
        else:
            # Default fallback
            rect = (screen_x + int(tile_size*0.1), screen_y + int(tile_size*0.1), int(tile_size*0.8), int(tile_size*0.8))
            pygame.draw.rect(self.screen, COLOR_ENTITY_DEFAULT, rect)

        # Highlight if selected
        if entity == self.selected_entity_id:
            # Breathing selection
            alpha = 255
            if self.time_manager:
                alpha = int(155 + 100 * math.sin(self.time_manager.real_time_elapsed * 5.0))
            
            sel_surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            pygame.draw.rect(sel_surface, (*COLOR_SELECTION, alpha), (0, 0, tile_size, tile_size), 3, border_radius=4)
            self.screen.blit(sel_surface, (screen_x, screen_y))
            
            # Draw Path
            if move_comp and move_comp.path:
                points = [(center_x, center_y)]
                for px, py in move_comp.path:
                    p_wx = px * self.base_pixels_per_unit + self.base_pixels_per_unit / 2
                    p_wy = py * self.base_pixels_per_unit + self.base_pixels_per_unit / 2
                    p_sx, p_sy = self.world_to_screen(p_wx, p_wy)
                    points.append((p_sx, p_sy))
                
                if len(points) > 1:
                    pygame.draw.lines(self.screen, COLOR_PATH, False, points, 2)

    def _draw_seasonal_tint(self):
        """Draw seasonal color tint overlay."""
        season = self.time_manager.get_season()
        
        # Create seasonal tint colors (subtle overlay)
        season_tints = {
            "spring": (0, 50, 0, 30),      # Green tint
            "summer": (50, 50, 0, 20),     # Bright yellow tint
            "autumn": (100, 80, 0, 40),    # Golden tint
            "winter": (200, 200, 255, 60)  # Snow white/blue tint
        }
        
        tint = season_tints.get(season, (0, 0, 0, 0))
        if tint[3] > 0:  # If alpha > 0
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill(tint)
            self.screen.blit(overlay, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2)
    
    def _draw_day_night_lighting(self):
        """Draw day/night lighting mask."""
        if not self.time_manager:
            return
        
        day_night_state = self.time_manager.get_day_night_state()
        hour = self.time_manager.time_of_day
        
        # Create lighting mask based on time of day
        # Note: pygame alpha is 0-255, but we'll use a brightness multiplier approach
        # Instead of dark overlay, we'll use a brightness factor (0.0 = dark, 1.0 = bright)
        
        if day_night_state == "night":
            # Dark overlay for night - use multiply blend with dark color
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            # Use a dark gray instead of pure black, with alpha for transparency
            overlay.fill((50, 50, 80, 180))  # Dark blue-gray with high alpha
            self.screen.blit(overlay, (0, 0), special_flags=pygame.BLEND_MULT)
        elif day_night_state == "dawn":
            # Gradual transition from night to day (5:00-7:00)
            # At 5:00: still dark (like night), at 7:00: bright (like day)
            # Progress: 0.0 at 5:00, 1.0 at 7:00
            progress = (hour - 5.0) / 2.0  # 0.0 to 1.0
            progress = max(0.0, min(1.0, progress))
            
            # Interpolate brightness: dark at 5:00 -> bright at 7:00
            # Use inverse: darkness decreases as progress increases
            # At progress=0 (5:00): alpha=150 (dark), at progress=1 (7:00): alpha=0 (bright)
            # Make it fade faster - only apply significant darkening early in dawn
            alpha = int(150 * (1.0 - progress) * (1.0 - progress))  # Quadratic fade for faster brightening
            
            # For dawn, use a warmer color (orange/yellow tint) instead of pure dark
            # Only apply if alpha is significant enough
            if alpha > 30:  # Only apply if still somewhat dark (threshold increased)
                overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
                # Warmer color for dawn: orange-yellow tint, but lighter
                # Use lighter base color so it doesn't darken too much
                overlay.fill((120, 100, 80, alpha))  # Lighter warm color
                self.screen.blit(overlay, (0, 0), special_flags=pygame.BLEND_MULT)
            # If alpha <= 30, it's bright enough, no overlay needed (dawn is bright)
        elif day_night_state == "dusk":
            # Gradual transition from day to night (19:00-21:00)
            # At 19:00: still bright (like day), at 21:00: dark (like night)
            # Progress: 0.0 at 19:00, 1.0 at 21:00
            progress = (hour - 19.0) / 2.0  # 0.0 to 1.0
            progress = max(0.0, min(1.0, progress))
            
            # Interpolate darkness: 0 (day) -> 180 (night)
            alpha = int(180 * progress)
            
            if alpha > 0:
                overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
                # Warmer color for dusk too
                overlay.fill((60, 40, 50, alpha))  # Warm dark with increasing alpha
                self.screen.blit(overlay, (0, 0), special_flags=pygame.BLEND_MULT)
        # Day: no overlay (normal brightness)


