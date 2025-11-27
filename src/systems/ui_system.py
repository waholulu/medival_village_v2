import pygame
import pygame_gui
from pygame_gui.elements import UIPanel, UILabel, UITextBox
from pygame_gui.core import ObjectID
from src.core.ecs import System

class UISystem(System):
    def __init__(self, screen: pygame.Surface, manager: pygame_gui.UIManager):
        self.screen = screen
        self.manager = manager
        
        screen_width, screen_height = screen.get_size()
        
        # --- God Panel (Top Right) ---
        panel_width = 250
        panel_height = 220  # Increased to fit season and day/night info
        self.god_panel = UIPanel(
            relative_rect=pygame.Rect((screen_width - panel_width - 10, 10), (panel_width, panel_height)),
            manager=self.manager,
            object_id=ObjectID(class_id='@god_panel', object_id='#god_panel')
        )
        
        self.fps_label = UILabel(
            relative_rect=pygame.Rect((10, 10), (200, 20)),
            text="FPS: 0",
            manager=self.manager,
            container=self.god_panel
        )
        
        self.time_label = UILabel(
            relative_rect=pygame.Rect((10, 35), (200, 20)),
            text="Time: Day 0 00:00",
            manager=self.manager,
            container=self.god_panel
        )
        
        self.cam_label = UILabel(
            relative_rect=pygame.Rect((10, 60), (200, 20)),
            text="Cam: (0, 0)",
            manager=self.manager,
            container=self.god_panel
        )

        self.zoom_label = UILabel(
            relative_rect=pygame.Rect((10, 85), (200, 20)),
            text="Zoom: 1.0x",
            manager=self.manager,
            container=self.god_panel
        )
        
        # Zone mode indicator
        self.zone_mode_label = UILabel(
            relative_rect=pygame.Rect((10, 110), (200, 20)),
            text="Zone Mode: OFF",
            manager=self.manager,
            container=self.god_panel
        )
        
        # Season indicator
        self.season_label = UILabel(
            relative_rect=pygame.Rect((10, 135), (200, 20)),
            text="Season: Spring",
            manager=self.manager,
            container=self.god_panel
        )
        
        # Day/Night indicator
        self.day_night_label = UILabel(
            relative_rect=pygame.Rect((10, 160), (200, 20)),
            text="Time: Day",
            manager=self.manager,
            container=self.god_panel
        )
        
        # --- Legend Panel (Right Side, Middle) ---
        legend_width = 250
        legend_height = 350
        legend_y = 240  # Below god panel with some spacing
        self.legend_panel = UIPanel(
            relative_rect=pygame.Rect((screen_width - legend_width - 10, legend_y), (legend_width, legend_height)),
            manager=self.manager,
            object_id=ObjectID(class_id='@legend_panel', object_id='#legend_panel')
        )
        
        UILabel(
            relative_rect=pygame.Rect((10, 10), (200, 20)),
            text="LEGEND",
            manager=self.manager,
            container=self.legend_panel
        )
        
        # Create legend content with color swatches and labels
        self.legend_content = UITextBox(
            relative_rect=pygame.Rect((10, 35), (220, 300)),
            html_text="",
            manager=self.manager,
            container=self.legend_panel
        )
        self._update_legend_content()
        
        # --- Inspector Panel (Bottom Right) ---
        inspector_height = 200
        self.inspector_panel = UIPanel(
            relative_rect=pygame.Rect((screen_width - panel_width - 10, screen_height - inspector_height - 10), (panel_width, inspector_height)),
            manager=self.manager,
            object_id=ObjectID(class_id='@inspector_panel', object_id='#inspector_panel')
        )
        
        UILabel(
            relative_rect=pygame.Rect((10, 10), (200, 20)),
            text="INSPECTOR",
            manager=self.manager,
            container=self.inspector_panel
        )
        
        self.inspector_content = UITextBox(
            relative_rect=pygame.Rect((10, 35), (210, 140)),
            html_text="Select a tile...",
            manager=self.manager,
            container=self.inspector_panel
        )

    def update_god_panel(self, fps: float, world_time_str: str, cam_pos: tuple, zoom: float, 
                         zone_mode: int = None, season: str = None, day_night_state: str = None):
        self.fps_label.set_text(f"FPS: {fps:.1f}")
        self.time_label.set_text(f"Time: {world_time_str}")
        self.cam_label.set_text(f"Cam: ({int(cam_pos[0])}, {int(cam_pos[1])})")
        self.zoom_label.set_text(f"Zoom: {zoom:.2f}x")
        
        # Update zone mode indicator
        if zone_mode is None:
            self.zone_mode_label.set_text("Zone Mode: OFF")
        else:
            from src.world.grid import ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL
            if zone_mode == ZONE_STOCKPILE:
                mode_name = "STOCKPILE"
            elif zone_mode == ZONE_FARM:
                mode_name = "FARM"
            elif zone_mode == ZONE_RESIDENTIAL:
                mode_name = "RESIDENTIAL"
            else:
                mode_name = "UNKNOWN"
            
            self.zone_mode_label.set_text(f"Zone Mode: {mode_name} [ACTIVE]")
        
        # Update season indicator
        if season:
            season_display = season.capitalize()
            self.season_label.set_text(f"Season: {season_display}")
        
        # Update day/night indicator
        if day_night_state:
            day_night_display = day_night_state.capitalize()
            self.day_night_label.set_text(f"Time: {day_night_display}")
        
    def _update_legend_content(self):
        """Update legend content with color explanations."""
        # Get color definitions from render system
        from src.systems.render_system import (
            COLOR_GRASS, COLOR_DIRT, COLOR_WATER, COLOR_STONE,
            COLOR_ENTITY_PLAYER, COLOR_ENTITY_TREE, COLOR_ENTITY_DEFAULT,
            COLOR_ZONE_STOCKPILE, COLOR_ZONE_FARM, COLOR_ZONE_RESIDENTIAL,
            COLOR_SELECTION, COLOR_PATH
        )
        
        # Helper function to convert RGB to hex for HTML
        def rgb_to_hex(rgb):
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        
        # Build HTML content
        html_content = "<b>TERRAIN:</b><br>"
        html_content += f'<font color="{rgb_to_hex(COLOR_GRASS)}">■</font> Grass<br>'
        html_content += f'<font color="{rgb_to_hex(COLOR_DIRT)}">■</font> Dirt<br>'
        html_content += f'<font color="{rgb_to_hex(COLOR_WATER)}">■</font> Water<br>'
        html_content += f'<font color="{rgb_to_hex(COLOR_STONE)}">■</font> Stone<br>'
        html_content += "<br><b>ZONES:</b><br>"
        html_content += f'<font color="{rgb_to_hex(COLOR_ZONE_STOCKPILE)}">■</font> Stockpile<br>'
        html_content += f'<font color="{rgb_to_hex(COLOR_ZONE_FARM)}">■</font> Farm<br>'
        html_content += f'<font color="{rgb_to_hex(COLOR_ZONE_RESIDENTIAL)}">■</font> Residential<br>'
        html_content += "<br><b>ENTITIES:</b><br>"
        html_content += f'<font color="{rgb_to_hex(COLOR_ENTITY_PLAYER)}">■</font> Villager<br>'
        html_content += f'<font color="{rgb_to_hex(COLOR_ENTITY_TREE)}">■</font> Tree<br>'
        html_content += f'<font color="{rgb_to_hex(COLOR_ENTITY_DEFAULT)}">■</font> Item/Crop<br>'
        html_content += "<br><b>UI:</b><br>"
        html_content += f'<font color="{rgb_to_hex(COLOR_SELECTION)}">■</font> Selection<br>'
        html_content += f'<font color="{rgb_to_hex(COLOR_PATH)}">■</font> Path<br>'
        
        self.legend_content.set_text(html_content)
    
    def update_inspector(self, tile_info: str):
        self.inspector_content.set_text(tile_info)

    def update(self, dt: float):
        self.manager.update(dt)
        self.manager.draw_ui(self.screen)

