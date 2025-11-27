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
from src.world.grid import Grid, TERRAIN_WATER, TERRAIN_STONE, ZONE_STOCKPILE
from src.world.zone_manager import ZoneManager
from src.systems.render_system import RenderSystem
from src.systems.ui_system import UISystem
from src.systems.action_system import ActionSystem
from src.systems.job_system import JobSystem, Job
from src.systems.ai_system import AISystem
from src.components.data_components import PositionComponent, MovementComponent, ActionComponent, ResourceComponent, InventoryComponent
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
    
    # New Phase 3 Managers
    zone_manager = ZoneManager(grid)
    job_system = JobSystem()
    
    # Systems
    action_system = ActionSystem(entity_manager, grid, config_manager)
    ai_system = AISystem(entity_manager, job_system, grid, zone_manager)

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
    # The Villager (previously Golem)
    villager = entity_manager.create_entity()
    entity_manager.add_component(villager, PositionComponent(10, 10))
    entity_manager.add_component(villager, MovementComponent(speed=config_manager.get("entities.villager.move_speed", 5.0)))
    entity_manager.add_component(villager, ActionComponent())
    entity_manager.add_component(villager, SkillComponent(skills=config_manager.get("entities.villager.default_skills", {"logging": 0.1})))
    entity_manager.add_component(villager, InventoryComponent(capacity=10)) # Add Inventory
    entity_manager.add_component(villager, IsPlayer())
    entity_manager.add_component(villager, IsSelectable())
    entity_manager.add_component(villager, IsWalkable())
    
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
    
    # Setup Phase 3 Test Scenario
    # 1. Mark Stockpile
    stockpile_pos = (20, 10)
    zone_manager.mark_zone(stockpile_pos[0], stockpile_pos[1], ZONE_STOCKPILE)
    Logger.info(f"Marked Stockpile at {stockpile_pos}")
    
    # 2. Create Chop Job
    chop_job = Job(
        job_type="chop",
        target_pos=(15, 10),
        target_entity_id=tree,
        required_skill="logging"
    )
    job_system.add_job(chop_job)
    Logger.info(f"Added Chop Job for Tree {tree}")
    
    Logger.info("Core systems initialized")
    Logger.info("Game Loop Started")

    # 5. Game Loop
    running = True
    clock = pygame.time.Clock()
    
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
            
            # Debug Selection
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
                    
                    # Info string
                    zone = grid.get_zone(*tile_pos)
                    zone_str = "None"
                    if zone == ZONE_STOCKPILE: zone_str = "Stockpile"
                    
                    info = f"Tile: {tile_pos}\nZone: {zone_str}"
                    if selected_id is not None:
                        info += f"\nEntity: {selected_id}"
                        inv = entity_manager.get_component(selected_id, InventoryComponent)
                        if inv: info += f"\nInv: {inv.items}"
                        
                        act = entity_manager.get_component(selected_id, ActionComponent)
                        if act: info += f"\nAction: {act.current_action}"
                        
                    ui_system.update_inspector(info)

            time_manager.update()
            
            # Update Logic Systems
            ai_system.update(dt)
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
            pygame.event.pump()
            
            time_manager.update()
            ai_system.update(dt)
            action_system.update(dt)
            
            # Logging (Every ~1 second)
            if time_manager.frame_count % 60 == 0:
                v_pos = entity_manager.get_component(villager, PositionComponent)
                v_act = entity_manager.get_component(villager, ActionComponent)
                v_inv = entity_manager.get_component(villager, InventoryComponent)
                
                log_msg = f"[Headless] Tick: {time_manager.frame_count} | Villager: ({v_pos.x}, {v_pos.y}) | Act: {v_act.current_action} | Inv: {v_inv.items}"
                Logger.info(log_msg)
                
                # Check Success Condition
                # 1. Tree gone? (ResourceComponent gone or Entity destroyed)
                # 2. Log in stockpile? (Or log entity on stockpile position)
                
                # Check items on stockpile
                from src.components.data_components import ItemComponent
                found_log_on_stockpile = False
                for e, item, pos in entity_manager.get_entities_with(ItemComponent, PositionComponent):
                    if pos.x == stockpile_pos[0] and pos.y == stockpile_pos[1] and item.item_type == "log":
                        found_log_on_stockpile = True
                        break
                
                if found_log_on_stockpile:
                    Logger.gameplay("TEST SUCCESS: Log hauled to stockpile!")
                    # We can exit or wait a bit
                    if time_manager.real_time_elapsed > 15.0:
                        break

            # Exit condition for test (timeout)
            if time_manager.real_time_elapsed > 30.0:
                Logger.info("Headless test timeout.")
                break
                
        clock.tick(tick_rate)

    config_manager.stop()
    pygame.quit()
    Logger.info("Game Terminated")

if __name__ == "__main__":
    main()
