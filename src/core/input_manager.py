import pygame
import pygame_gui
from typing import Optional, Tuple
from src.utils.logger import Logger, LogCategory

class InputManager:
    def __init__(self, ui_manager: pygame_gui.UIManager):
        self.ui_manager = ui_manager
        
        # Logical states
        self.camera_move_vector = [0, 0] # [x, y]
        self.zoom_change = 0
        self.selected_tile: Optional[Tuple[int, int]] = None
        self.should_quit = False
        self.is_paused = False
        self.time_scale_request: Optional[float] = None
        
        self.last_command = None # {'type': str, ...}

        # Key mappings
        self.key_map = {
            pygame.K_w: (0, -1),
            pygame.K_s: (0, 1),
            pygame.K_a: (-1, 0),
            pygame.K_d: (1, 0),
            pygame.K_UP: (0, -1),
            pygame.K_DOWN: (0, 1),
            pygame.K_LEFT: (-1, 0),
            pygame.K_RIGHT: (1, 0)
        }

    def process_events(self, screen_to_world_callback=None):
        """
        Process all pygame events and update state.
        screen_to_world_callback: function(x, y) -> (world_x, world_y)
        """
        self.camera_move_vector = [0, 0]
        self.zoom_change = 0
        self.time_scale_request = None
        self.last_command = None
        
        for event in pygame.event.get():
            # Pass event to UI Manager first
            self.ui_manager.process_events(event)
            
            if event.type == pygame.QUIT:
                self.should_quit = True
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.should_quit = True
                elif event.key == pygame.K_SPACE:
                    self.is_paused = not self.is_paused
                    status = "PAUSED" if self.is_paused else "RESUMED"
                    Logger.log(LogCategory.INPUT, f"Game {status}")
                elif event.key == pygame.K_1:
                    self.time_scale_request = 1.0
                elif event.key == pygame.K_2:
                    self.time_scale_request = 2.0
                elif event.key == pygame.K_3:
                    self.time_scale_request = 5.0
            
            elif event.type == pygame.MOUSEWHEEL:
                self.zoom_change = event.y # +1 or -1 typically
                
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left Click
                    if not self.ui_manager.get_hovering_any_element(): # Ignore clicks on UI
                        if screen_to_world_callback:
                             wx, wy = screen_to_world_callback(event.pos[0], event.pos[1])
                             # We can decide if this is a move or select command here, 
                             # or just pass the world coordinate up.
                             # For now, let's assume right click is move? Or left click is select/move?
                             # The plan implies Right Click for move (Phase 2: "Right key click tree...").
                             # Wait, the plan says "Right click tree...".
                             # Let's check button. Button 1 is Left, Button 3 is Right.
                             pass

                elif event.button == 3: # Right Click
                     if screen_to_world_callback:
                         wx, wy = screen_to_world_callback(event.pos[0], event.pos[1])
                         self.last_command = {'type': 'INTERACT_OR_MOVE', 'world_pos': (wx, wy)}
                    
        # Continuous Key State for smooth movement
        keys = pygame.key.get_pressed()
        for key, (dx, dy) in self.key_map.items():
            if keys[key]:
                self.camera_move_vector[0] += dx
                self.camera_move_vector[1] += dy

                
    def get_camera_movement(self) -> Tuple[float, float]:
        return tuple(self.camera_move_vector)
        
    def get_zoom_change(self) -> int:
        return self.zoom_change

    def get_mouse_pos(self) -> Tuple[int, int]:
        return pygame.mouse.get_pos()

    def is_left_click_just_pressed(self) -> bool:
        return pygame.mouse.get_pressed()[0]
