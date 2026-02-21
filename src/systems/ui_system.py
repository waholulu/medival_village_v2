import pygame
import pygame_gui
from pygame_gui.elements import UIPanel, UILabel, UITextBox, UIButton
from pygame_gui.core import ObjectID
from src.core.ecs import System, EntityManager

class UISystem(System):
    def __init__(self, screen: pygame.Surface, manager: pygame_gui.UIManager, entity_manager: EntityManager = None):
        self.screen = screen
        self.manager = manager
        self.entity_manager = entity_manager
        self.selected_villager_id = None
        self.villager_buttons = {}  # Map entity_id -> UIButton
        
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
        
        # --- Villager Panel (Left Side) ---
        villager_panel_width = 280
        villager_panel_height = screen_height - 20
        detail_panel_height = 280
        list_container_height = villager_panel_height - detail_panel_height - 50  # Reserve space for detail panel and header
        
        self.villager_panel = UIPanel(
            relative_rect=pygame.Rect((10, 10), (villager_panel_width, villager_panel_height)),
            manager=self.manager,
            object_id=ObjectID(class_id='@villager_panel', object_id='#villager_panel')
        )
        
        UILabel(
            relative_rect=pygame.Rect((10, 10), (200, 20)),
            text="VILLAGERS",
            manager=self.manager,
            container=self.villager_panel
        )
        
        # Scrollable container for villager list (top part)
        self.villager_list_container = UIPanel(
            relative_rect=pygame.Rect((5, 35), (villager_panel_width - 10, list_container_height)),
            manager=self.manager,
            container=self.villager_panel
        )
        
        # Detailed villager info panel (bottom part of villager panel)
        self.villager_detail_panel = UIPanel(
            relative_rect=pygame.Rect((5, 35 + list_container_height + 5), (villager_panel_width - 10, detail_panel_height)),
            manager=self.manager,
            container=self.villager_panel,
            object_id=ObjectID(class_id='@villager_detail_panel', object_id='#villager_detail_panel')
        )
        
        UILabel(
            relative_rect=pygame.Rect((10, 10), (200, 20)),
            text="DETAILS",
            manager=self.manager,
            container=self.villager_detail_panel
        )
        
        self.villager_detail_content = UITextBox(
            relative_rect=pygame.Rect((10, 35), (villager_panel_width - 30, detail_panel_height - 45)),
            html_text="Click a villager to see details...",
            manager=self.manager,
            container=self.villager_detail_panel
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
    
    def update_villager_panel(self):
        """Update the villager panel with current villager status."""
        if not self.entity_manager:
            return
        
        from src.components.tags import IsVillager
        from src.components.data_components import (
            PositionComponent, HungerComponent, TirednessComponent, 
            MoodComponent, ActionComponent, JobComponent, RoutineComponent,
            InventoryComponent, ColdComponent, SleepStateComponent
        )
        from src.components.skill_component import SkillComponent
        
        # Get all villagers
        villagers = []
        for entity, _ in self.entity_manager.get_entities_with(IsVillager):
            villagers.append(entity)
        
        # Remove old buttons that no longer exist
        existing_villagers = set(villagers)
        buttons_to_remove = [eid for eid in self.villager_buttons.keys() if eid not in existing_villagers]
        for eid in buttons_to_remove:
            self.villager_buttons[eid].kill()
            del self.villager_buttons[eid]
        
        # Create/update buttons for each villager
        button_height = 80
        button_width = 260
        button_spacing = 5
        y_offset = 5
        
        for i, villager_id in enumerate(villagers):
            # Get villager data
            pos = self.entity_manager.get_component(villager_id, PositionComponent)
            hunger = self.entity_manager.get_component(villager_id, HungerComponent)
            tiredness = self.entity_manager.get_component(villager_id, TirednessComponent)
            mood = self.entity_manager.get_component(villager_id, MoodComponent)
            action = self.entity_manager.get_component(villager_id, ActionComponent)
            job = self.entity_manager.get_component(villager_id, JobComponent)
            routine = self.entity_manager.get_component(villager_id, RoutineComponent)
            cold = self.entity_manager.get_component(villager_id, ColdComponent)
            
            # Create button if it doesn't exist
            if villager_id not in self.villager_buttons:
                button = UIButton(
                    relative_rect=pygame.Rect((5, y_offset + i * (button_height + button_spacing), button_width, button_height)),
                    text="",  # Text will be set below
                    manager=self.manager,
                    container=self.villager_list_container,
                    object_id=ObjectID(class_id='@villager_button', object_id=f'#villager_{villager_id}')
                )
                self.villager_buttons[villager_id] = button
            
            # Update button text with villager status
            button = self.villager_buttons[villager_id]
            
            # Build status text (plain text, no HTML)
            villager_name = f"Villager {villager_id}"
            
            # Needs summary with status indicators
            needs_parts = []
            if hunger:
                hunger_status = "R" if hunger.hunger > 80 else "Y" if hunger.hunger > 50 else "G"
                needs_parts.append(f"H{hunger_status}:{hunger.hunger:.0f}")
            if tiredness:
                tired_status = "R" if tiredness.tiredness > 80 else "Y" if tiredness.tiredness > 50 else "G"
                needs_parts.append(f"T{tired_status}:{tiredness.tiredness:.0f}")
            if mood:
                mood_status = "R" if mood.mood < 30 else "Y" if mood.mood < 70 else "G"
                needs_parts.append(f"M{mood_status}:{mood.mood:.0f}")
            if cold:
                cold_status = "R" if cold.cold > 70 else "Y" if cold.cold > 40 else "G"
                needs_parts.append(f"C{cold_status}:{cold.cold:.0f}")
            
            needs_str = " ".join(needs_parts) if needs_parts else ""
            
            # Current activity
            activity = "Idle"
            if routine and routine.current_state:
                activity = routine.current_state
            elif action and action.current_action != "idle":
                activity = action.current_action
            elif job:
                activity = f"Job:{job.job_type}"
            
            # Build button text (plain text, newlines for multi-line)
            if pos:
                button_text = f"{villager_name}\n({pos.x},{pos.y}) {needs_str}\n{activity}"
            else:
                button_text = f"{villager_name}\n{needs_str}\n{activity}"
            
            button.set_text(button_text)
            
            # Highlight selected villager
            if villager_id == self.selected_villager_id:
                button.select()
            else:
                button.unselect()
    
    def handle_ui_event(self, event):
        """Handle UI events, particularly villager button clicks."""
        # Check if this is a UI event with a ui_element
        if hasattr(event, 'ui_element') and event.ui_element is not None:
            # Check if the clicked element is one of our villager buttons
            for villager_id, button in self.villager_buttons.items():
                if event.ui_element == button:
                    self.selected_villager_id = villager_id
                    self._update_villager_details(villager_id)
                    break
    
    def _update_villager_details(self, villager_id: int):
        """Update the detailed villager info panel."""
        if not self.entity_manager:
            return
        
        from src.components.tags import IsVillager, IsPlayer
        from src.components.data_components import (
            PositionComponent, HungerComponent, TirednessComponent, 
            MoodComponent, ActionComponent, JobComponent, RoutineComponent,
            InventoryComponent, ColdComponent, SleepStateComponent,
            MovementComponent
        )
        from src.components.skill_component import SkillComponent
        
        # Check if it's actually a villager
        if not self.entity_manager.has_component(villager_id, IsVillager):
            return
        
        # Build detailed info
        info_lines = [f"<b>=== Villager {villager_id} ==</b>"]
        
        # Type
        if self.entity_manager.has_component(villager_id, IsPlayer):
            info_lines.append("Type: Player Villager")
        else:
            info_lines.append("Type: Villager")
        
        # Position
        pos = self.entity_manager.get_component(villager_id, PositionComponent)
        if pos:
            info_lines.append(f"Position: ({pos.x}, {pos.y})")
        
        # Skills
        skill_comp = self.entity_manager.get_component(villager_id, SkillComponent)
        if skill_comp and skill_comp.skills:
            info_lines.append("<b>Skills:</b>")
            for skill_name, skill_level in skill_comp.skills.items():
                info_lines.append(f"  • {skill_name}: {skill_level*100:.1f}%")
        
        # Needs
        info_lines.append("<b>Needs:</b>")
        hunger = self.entity_manager.get_component(villager_id, HungerComponent)
        tiredness = self.entity_manager.get_component(villager_id, TirednessComponent)
        mood = self.entity_manager.get_component(villager_id, MoodComponent)
        cold = self.entity_manager.get_component(villager_id, ColdComponent)
        
        if hunger:
            hunger_status = "Low" if hunger.hunger < 50 else "Medium" if hunger.hunger < 80 else "High"
            info_lines.append(f"  • Hunger: {hunger.hunger:.1f}/100 ({hunger_status})")
        if tiredness:
            tired_status = "Low" if tiredness.tiredness < 50 else "Medium" if tiredness.tiredness < 90 else "High"
            info_lines.append(f"  • Tiredness: {tiredness.tiredness:.1f}/100 ({tired_status})")
        if mood:
            mood_status = "Poor" if mood.mood < 30 else "Fair" if mood.mood < 70 else "Good"
            info_lines.append(f"  • Mood: {mood.mood:.1f}/100 ({mood_status})")
        if cold:
            cold_status = "Low" if cold.cold < 40 else "Medium" if cold.cold < 70 else "High"
            info_lines.append(f"  • Cold: {cold.cold:.1f}/100 ({cold_status})")
        
        # Action & Movement
        act = self.entity_manager.get_component(villager_id, ActionComponent)
        if act:
            info_lines.append(f"<b>Action:</b> {act.current_action}")
            if act.target_entity_id:
                info_lines.append(f"Target Entity: {act.target_entity_id}")
            if act.target_pos:
                info_lines.append(f"Target Pos: {act.target_pos}")
        
        move_comp = self.entity_manager.get_component(villager_id, MovementComponent)
        if move_comp:
            if move_comp.target:
                info_lines.append(f"Moving to: {move_comp.target}")
            if move_comp.path:
                info_lines.append(f"Path length: {len(move_comp.path)} tiles")
            info_lines.append(f"Speed: {move_comp.speed:.1f}")
        
        # Job
        job_comp = self.entity_manager.get_component(villager_id, JobComponent)
        if job_comp:
            info_lines.append(f"<b>Job:</b> {job_comp.job_type} (ID: {job_comp.job_id})")
            if job_comp.target_pos:
                info_lines.append(f"Job Target: {job_comp.target_pos}")
        else:
            info_lines.append("<b>Job:</b> None")
        
        # Routine
        routine = self.entity_manager.get_component(villager_id, RoutineComponent)
        if routine:
            info_lines.append(f"<b>Routine State:</b> {routine.current_state}")
            if routine.next_scheduled_activity:
                info_lines.append(f"Next Activity: {routine.next_scheduled_activity}")
        
        # Sleep state
        sleep_state = self.entity_manager.get_component(villager_id, SleepStateComponent)
        if sleep_state:
            info_lines.append(f"<b>Sleeping:</b> {'Yes' if sleep_state.is_sleeping else 'No'}")
            if sleep_state.sleep_location:
                info_lines.append(f"Sleep Location: {sleep_state.sleep_location}")
        
        # Inventory
        inv = self.entity_manager.get_component(villager_id, InventoryComponent)
        if inv:
            total_items = sum(inv.items.values())
            info_lines.append(f"<b>Inventory:</b> {len(inv.items)} types, {total_items} items")
            if inv.items:
                for item_type, amount in inv.items.items():
                    info_lines.append(f"  • {item_type}: {amount}")
            else:
                info_lines.append("  (empty)")
            info_lines.append(f"Capacity: {inv.capacity}")
        
        # Set the detail text
        detail_text = "<br>".join(info_lines)
        self.villager_detail_content.set_text(detail_text)

    def update(self, dt: float):
        self.manager.update(dt)
        self.manager.draw_ui(self.screen)

