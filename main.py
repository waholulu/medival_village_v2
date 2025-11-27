import pygame
import pygame_gui
import json
import os
import argparse
import sys
from src.core.ecs import EntityManager
from src.core.time_manager import TimeManager
from src.core.input_manager import InputManager
from src.core.config_manager import ConfigManager
from src.world.grid import Grid, TERRAIN_WATER, TERRAIN_STONE
from src.systems.render_system import RenderSystem
from src.systems.ui_system import UISystem
from src.systems.action_system import ActionSystem
from src.components.data_components import PositionComponent, MovementComponent, ActionComponent, ResourceComponent
from src.components.skill_component import SkillComponent
from src.components.tags import IsWalkable, IsTree, IsSelectable, IsPlayer
from src.utils.logger import Logger, LogCategory

def main():
    # 0. Parse Arguments
    parser = argparse.ArgumentParser(description="Project Medieval Game")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no GUI)")
    args = parser.parse_args()

    # 1. Initialization
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    
    pygame.init()
    
    # Config Manager
    config_manager = ConfigManager("config/balance.json")
    global_conf = config_manager.get("global", {})
    
    tick_rate = global_conf.get("tick_rate", 60)
    
    # 2. Core Systems Setup (Common)
    time_manager = TimeManager(tick_rate=tick_rate)
    Logger.set_time_manager(time_manager)
    entity_manager = EntityManager()
    
    # World Generation (Test Data)
    pixels_per_unit = global_conf.get("pixels_per_unit", 32)
    width = global_conf.get("screen_width", 1280)
    height = global_conf.get("screen_height", 720)
    map_width = width // pixels_per_unit + 5
    map_height = height // pixels_per_unit + 5
    grid = Grid(map_width, map_height)
    
    # Create some test terrain
    grid.set_terrain(5, 5, TERRAIN_WATER)
    grid.set_terrain(6, 5, TERRAIN_WATER)
    grid.set_terrain(7, 5, TERRAIN_WATER)
    grid.set_terrain(2, 2, TERRAIN_STONE)
    
    # Action System (Common)
    action_system = ActionSystem(entity_manager, grid, config_manager)

    # 3. Graphics Setup (Conditional)
    screen = None
    ui_manager = None
    input_manager = None
    render_system = None
    ui_system = None
    
    if not args.headless:
        screen_width = global_conf.get("screen_width", 1280)
        screen_height = global_conf.get("screen_height", 720)
        title = global_conf.get("title", "Project Medieval")
        
        screen = pygame.display.set_mode((screen_width, screen_height))
        pygame.display.set_caption(title)
        
        ui_manager = pygame_gui.UIManager((screen_width, screen_height))
        input_manager = InputManager(ui_manager)
        
        render_system = RenderSystem(screen, grid, entity_manager, config_manager.config)
        ui_system = UISystem(screen, ui_manager)
        
        Logger.info("Graphical systems initialized")
    else:
        Logger.info("Running in Headless Mode")

    # 4. Spawn Test Entities (Common)
    # The Golem
    golem = entity_manager.create_entity()
    entity_manager.add_component(golem, PositionComponent(10, 10))
    entity_manager.add_component(golem, MovementComponent(speed=config_manager.get("entities.villager.move_speed", 5.0)))
    entity_manager.add_component(golem, ActionComponent())
    entity_manager.add_component(golem, SkillComponent(skills=config_manager.get("entities.villager.default_skills", {})))
    entity_manager.add_component(golem, IsPlayer())
    entity_manager.add_component(golem, IsSelectable())
    entity_manager.add_component(golem, IsWalkable())
    
    # A Tree
    tree = entity_manager.create_entity()
    entity_manager.add_component(tree, PositionComponent(15, 10))
    entity_manager.add_component(tree, ResourceComponent(
        resource_type="tree_oak", 
        health=config_manager.get("entities.tree_oak.hp", 20), 
        max_health=config_manager.get("entities.tree_oak.hp", 20)
    ))
    entity_manager.add_component(tree, IsTree())
    entity_manager.add_component(tree, IsSelectable())
    
    Logger.info("Core systems initialized")
    Logger.info("Game Loop Started")

    # 5. Game Loop
    running = True
    clock = pygame.time.Clock()
    
    # Headless Test Setup
    if args.headless:
        # Auto-Test: Move Golem to (20, 20)
        target_x, target_y = 20, 20
        Logger.gameplay(f"Headless Test: Commanding Golem {golem} to move to ({target_x}, {target_y})")
        
        action_comp = entity_manager.get_component(golem, ActionComponent)
        move_comp = entity_manager.get_component(golem, MovementComponent)
        
        if action_comp and move_comp:
            action_comp.current_action = "move"
            move_comp.target = (target_x, target_y)
            move_comp.path = [] # Force recalc

    while running:
        dt = time_manager.get_delta_time()
        
        if not args.headless:
            # --- Graphical Loop ---
            # Input Handling
            def convert_screen_to_world(x, y):
                 return render_system.screen_to_world(x, y)

            input_manager.process_events(convert_screen_to_world)
            
            if input_manager.should_quit:
                running = False
                
            # Handle Pause
            if input_manager.is_paused != time_manager.is_paused:
                time_manager.toggle_pause()
                
            # Handle Time Scale
            if input_manager.time_scale_request is not None:
                time_manager.set_time_scale(input_manager.time_scale_request)
                Logger.info(f"Time scale set to {input_manager.time_scale_request}")

            # Handle Camera Movement
            move_vec = input_manager.get_camera_movement()
            if move_vec[0] != 0 or move_vec[1] != 0:
                camera_speed_multiplier = 1.0 / 60.0 
                render_system.move_camera(move_vec[0] * camera_speed_multiplier, 
                                          move_vec[1] * camera_speed_multiplier)
                
            # Handle Zoom
            zoom_change = input_manager.get_zoom_change()
            if zoom_change != 0:
                render_system.adjust_zoom(zoom_change)
                
            # Handle Commands from Input
            if input_manager.last_command:
                cmd = input_manager.last_command
                if cmd['type'] == 'INTERACT_OR_MOVE':
                     wx, wy = cmd['world_pos']
                     tx = int(wx / pixels_per_unit)
                     ty = int(wy / pixels_per_unit)
                     
                     if render_system.selected_entity_id is not None:
                         actor = render_system.selected_entity_id
                         action_comp = entity_manager.get_component(actor, ActionComponent)
                         move_comp = entity_manager.get_component(actor, MovementComponent)
                         
                         if action_comp and move_comp:
                             target_id = None
                             for e, pos in entity_manager.get_entities_with(PositionComponent):
                                 if pos.x == tx and pos.y == ty and e != actor:
                                     target_id = e
                                     break
                             
                             if target_id is not None and entity_manager.has_component(target_id, IsTree):
                                 Logger.gameplay(f"Command: Chop tree {target_id}")
                                 action_comp.current_action = "chop"
                                 action_comp.target_entity_id = target_id
                                 move_comp.target = (tx, ty)
                                 move_comp.path = [] 
                             else:
                                 Logger.gameplay(f"Command: Move to {tx}, {ty}")
                                 action_comp.current_action = "move"
                                 action_comp.target_entity_id = None
                                 move_comp.target = (tx, ty)
                                 move_comp.path = [] 

            # Handle Selection
            if input_manager.is_left_click_just_pressed():
                if not ui_manager.get_hovering_any_element():
                    mx, my = input_manager.get_mouse_pos()
                    tile_pos = render_system.get_tile_at_screen_pos(mx, my)
                    render_system.selected_tile = tile_pos
                    
                    selected_id = None
                    for e, pos, _ in entity_manager.get_entities_with(PositionComponent, IsSelectable):
                        if pos.x == tile_pos[0] and pos.y == tile_pos[1]:
                            selected_id = e
                            break
                    
                    render_system.selected_entity_id = selected_id
                    
                    terrain_id = grid.get_terrain(*tile_pos)
                    walkable = grid.is_walkable(*tile_pos)
                    info = f"Tile: {tile_pos}\nTerrain ID: {terrain_id}\nWalkable: {walkable}"
                    if selected_id is not None:
                        info += f"\nEntity: {selected_id}"
                        res = entity_manager.get_component(selected_id, ResourceComponent)
                        if res:
                            info += f"\nHP: {res.health}/{res.max_health}"
                        act = entity_manager.get_component(selected_id, ActionComponent)
                        if act:
                            info += f"\nAction: {act.current_action}"
                        skills = entity_manager.get_component(selected_id, SkillComponent)
                        if skills:
                            info += f"\nSkills: {skills.skills}"
                    
                    ui_system.update_inspector(info)
                    Logger.gameplay(f"Selected tile {tile_pos}, Entity: {selected_id}")

            time_manager.update()
            action_system.update(dt)
            render_system.update(dt)
            
            ui_system.update_god_panel(
                fps=time_manager.fps,
                world_time_str=f"Day {time_manager.day} {int(time_manager.time_of_day):02d}:00",
                cam_pos=render_system.camera_pos,
                zoom=render_system.zoom_level
            )
            ui_system.update(dt)
            
            pygame.display.flip()
        else:
            # --- Headless Loop ---
            # 1. Event Pump (Required for Pygame internals even without display)
            pygame.event.pump()
            
            # 2. Update Logic
            time_manager.update()
            action_system.update(dt)
            
            # 3. Logging (Every 60 ticks ~ 1 second)
            # We use frame_count (which is essentially ticks since start)
            # If we want strictly every second, we can check time, but frame_count is easier for determinstic-ish behavior
            if time_manager.frame_count % 60 == 0:
                # Get Golem Position
                golem_pos = entity_manager.get_component(golem, PositionComponent)
                Logger.info(f"[Headless] Tick: {time_manager.frame_count} | FPS: {time_manager.fps:.2f} | Golem Pos: ({golem_pos.x}, {golem_pos.y})")
                
                # Check if reached destination (approx check if exact match might be missed due to float, but grid is int)
                if golem_pos.x == 20 and golem_pos.y == 20:
                     Logger.gameplay("Test SUCCESS: Golem reached (20, 20)")
                     # For this test run, we can exit shortly after success, or let it run to 600
                     
            # Exit condition for test (e.g. after 10 seconds)
            if time_manager.real_time_elapsed > 10.0:
                Logger.info(f"Headless test run complete ({time_manager.real_time_elapsed:.2f}s). Exiting.")
                running = False
                break
                
        clock.tick(tick_rate)

    config_manager.stop()
    pygame.quit()
    Logger.info("Game Terminated")

if __name__ == "__main__":
    main()
