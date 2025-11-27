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
        panel_height = 170  # Increased to fit zone mode indicator
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

    def update_god_panel(self, fps: float, world_time_str: str, cam_pos: tuple, zoom: float, zone_mode: int = None):
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
        
    def update_inspector(self, tile_info: str):
        self.inspector_content.set_text(tile_info)

    def update(self, dt: float):
        self.manager.update(dt)
        self.manager.draw_ui(self.screen)

