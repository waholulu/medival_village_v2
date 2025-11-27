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
from src.world.grid import Grid, TERRAIN_WATER, TERRAIN_STONE, ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL, ZONE_NONE
from src.world.zone_manager import ZoneManager
from src.systems.render_system import RenderSystem
from src.systems.ui_system import UISystem
from src.systems.action_system import ActionSystem
from src.systems.job_system import JobSystem, Job
from src.systems.ai_system import AISystem
from src.systems.needs_system import NeedsSystem
from src.systems.farming_system import FarmingSystem
from src.systems.routine_system import RoutineSystem
from src.components.data_components import PositionComponent, MovementComponent, ActionComponent, ResourceComponent, InventoryComponent, HungerComponent, TirednessComponent, MoodComponent, RoutineComponent, ItemComponent
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
    sim_conf = config_manager.get("simulation", {})
    day_length = sim_conf.get("day_length_seconds", 600.0)
    season_length = sim_conf.get("season_length_days", 90)
    starting_season = sim_conf.get("starting_season", "spring")
    
    # 2. Core Systems Setup (Common)
    time_manager = TimeManager(tick_rate=tick_rate, day_length_seconds=day_length, 
                               season_length_days=season_length, starting_season=starting_season)
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
    needs_system = NeedsSystem(entity_manager, time_manager, config_manager)
    farming_system = FarmingSystem(entity_manager, job_system, grid, zone_manager, time_manager, config_manager)
    routine_system = RoutineSystem(entity_manager, time_manager, config_manager)

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
        
        render_system = RenderSystem(screen, grid, entity_manager, config_manager.config, zone_manager, time_manager)
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
    entity_manager.add_component(villager, HungerComponent(hunger=20.0))  # Start with some hunger
    entity_manager.add_component(villager, TirednessComponent(tiredness=10.0))  # Start with some tiredness
    entity_manager.add_component(villager, MoodComponent(mood=70.0))  # Start with good mood
    entity_manager.add_component(villager, RoutineComponent())  # Daily routine
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
    
    # Setup Phase 4 Test Scenario
    # 1. Mark Stockpile
    stockpile_pos = (20, 10)
    zone_manager.mark_zone(stockpile_pos[0], stockpile_pos[1], ZONE_STOCKPILE)
    Logger.info(f"Marked Stockpile at {stockpile_pos}")
    
    # Test zone setting (for both headless and graphical modes)
    # Set additional zones for testing
    farm_pos = (25, 10)
    residential_pos = (30, 10)
    zone_manager.mark_zone(farm_pos[0], farm_pos[1], ZONE_FARM)
    zone_manager.mark_zone(residential_pos[0], residential_pos[1], ZONE_RESIDENTIAL)
    Logger.info(f"Test: Set Farm zone at {farm_pos}")
    Logger.info(f"Test: Set Residential zone at {residential_pos}")
    
    # Add some test food items for survival testing
    food_entity = entity_manager.create_entity()
    entity_manager.add_component(food_entity, PositionComponent(x=12, y=10))
    entity_manager.add_component(food_entity, ItemComponent(item_type="food_wheat", amount=3, food_value=30.0))
    Logger.info("Test: Created food item at (12, 10)")
    
    # Add some seeds for farming
    seed_entity = entity_manager.create_entity()
    entity_manager.add_component(seed_entity, PositionComponent(x=14, y=10))
    entity_manager.add_component(seed_entity, ItemComponent(item_type="seed_wheat", amount=5))
    Logger.info("Test: Created seed item at (14, 10)")
    
    # Verify zones are set correctly
    assert grid.get_zone(stockpile_pos[0], stockpile_pos[1]) == ZONE_STOCKPILE, "Stockpile zone not set correctly"
    assert grid.get_zone(25, 10) == ZONE_FARM, "Farm zone not set correctly"
    assert grid.get_zone(30, 10) == ZONE_RESIDENTIAL, "Residential zone not set correctly"
    Logger.info("Test: All zones verified successfully")
    
    # Test zone query
    nearest_stockpile = zone_manager.get_nearest_zone_tile((15, 10), ZONE_STOCKPILE)
    assert nearest_stockpile == stockpile_pos, f"Nearest stockpile query failed: got {nearest_stockpile}, expected {stockpile_pos}"
    Logger.info(f"Test: Nearest stockpile query works: {nearest_stockpile}")
    
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
            
            # Handle Commands from Input
            if input_manager.last_command:
                cmd = input_manager.last_command
                if cmd['type'] == 'SET_ZONE':
                    # Place zone at clicked position
                    wx, wy = cmd['world_pos']
                    tx = int(wx / pixels_per_unit)
                    ty = int(wy / pixels_per_unit)
                    zone_type = cmd['zone_type']
                    
                    zone_manager.mark_zone(tx, ty, zone_type)
                    zone_name = "Stockpile" if zone_type == ZONE_STOCKPILE else \
                               "Farm" if zone_type == ZONE_FARM else \
                               "Residential" if zone_type == ZONE_RESIDENTIAL else "Unknown"
                    Logger.gameplay(f"Placed {zone_name} zone at ({tx}, {ty})")
                    
                elif cmd['type'] == 'INTERACT_OR_MOVE':
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
                    elif zone == ZONE_FARM: zone_str = "Farm"
                    elif zone == ZONE_RESIDENTIAL: zone_str = "Residential"
                    
                    # Show zone placement mode
                    zone_mode = input_manager.get_zone_placement_mode()
                    mode_str = ""
                    if zone_mode == ZONE_STOCKPILE: mode_str = "\n[Mode: Stockpile Placement - Right-click to place]"
                    elif zone_mode == ZONE_FARM: mode_str = "\n[Mode: Farm Placement - Right-click to place]"
                    elif zone_mode == ZONE_RESIDENTIAL: mode_str = "\n[Mode: Residential Placement - Right-click to place]"
                    
                    info = f"Tile: {tile_pos}\nZone: {zone_str}{mode_str}"
                    if selected_id is not None:
                        info += f"\nEntity: {selected_id}"
                        inv = entity_manager.get_component(selected_id, InventoryComponent)
                        if inv: info += f"\nInv: {inv.items}"
                        
                        act = entity_manager.get_component(selected_id, ActionComponent)
                        if act: info += f"\nAction: {act.current_action}"
                        
                        # Show needs if villager
                        hunger = entity_manager.get_component(selected_id, HungerComponent)
                        tiredness = entity_manager.get_component(selected_id, TirednessComponent)
                        mood = entity_manager.get_component(selected_id, MoodComponent)
                        if hunger:
                            hunger_color = "green" if hunger.hunger < 50 else "yellow" if hunger.hunger < 80 else "red"
                            info += f"\nHunger: {hunger.hunger:.1f}/100 ({hunger_color})"
                        if tiredness:
                            tired_color = "green" if tiredness.tiredness < 50 else "yellow" if tiredness.tiredness < 90 else "red"
                            info += f"\nTiredness: {tiredness.tiredness:.1f}/100 ({tired_color})"
                        if mood:
                            mood_color = "red" if mood.mood < 30 else "yellow" if mood.mood < 70 else "green"
                            info += f"\nMood: {mood.mood:.1f}/100 ({mood_color})"
                        
                        # Show crop info if crop
                        from src.components.data_components import CropComponent
                        crop = entity_manager.get_component(selected_id, CropComponent)
                        if crop:
                            info += f"\nCrop: {crop.crop_type}\nState: {crop.state}\nProgress: {crop.growth_progress*100:.1f}%"
                        
                    ui_system.update_inspector(info)

            time_manager.update()
            
            # Update Logic Systems
            needs_system.update(dt)
            routine_system.update(dt)
            farming_system.update(dt)
            ai_system.update(dt)
            action_system.update(dt)
            
            render_system.update(dt)
            ui_system.update_god_panel(
                fps=time_manager.fps,
                world_time_str=f"Day {time_manager.day} {int(time_manager.time_of_day):02d}:{int((time_manager.time_of_day % 1.0) * 60):02d}",
                cam_pos=render_system.camera_pos,
                zoom=render_system.zoom_level,
                zone_mode=input_manager.get_zone_placement_mode(),
                season=time_manager.get_season(),
                day_night_state=time_manager.get_day_night_state()
            )
            ui_system.update(dt)
            
            pygame.display.flip()
        else:
            # --- Headless Loop ---
            pygame.event.pump()
            
            time_manager.update()
            needs_system.update(dt)
            routine_system.update(dt)
            farming_system.update(dt)
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
                found_log_on_stockpile = False
                for e, item, pos in entity_manager.get_entities_with(ItemComponent, PositionComponent):
                    if pos.x == stockpile_pos[0] and pos.y == stockpile_pos[1] and item.item_type == "log":
                        found_log_on_stockpile = True
                        break
                
                # Test zone queries during runtime (every 5 seconds)
                if time_manager.frame_count % 300 == 0:
                    # Verify zones still exist
                    stockpile_zone = grid.get_zone(stockpile_pos[0], stockpile_pos[1])
                    farm_zone = grid.get_zone(25, 10)
                    residential_zone = grid.get_zone(30, 10)
                    
                    Logger.info(f"[Zone Test] Stockpile at {stockpile_pos}: {stockpile_zone} (expected {ZONE_STOCKPILE})")
                    Logger.info(f"[Zone Test] Farm at (25, 10): {farm_zone} (expected {ZONE_FARM})")
                    Logger.info(f"[Zone Test] Residential at (30, 10): {residential_zone} (expected {ZONE_RESIDENTIAL})")
                    
                    # Test zone removal and re-adding
                    if time_manager.frame_count == 300:  # Only once
                        Logger.info("[Zone Test] Testing zone removal...")
                        zone_manager.mark_zone(25, 10, ZONE_NONE)
                        assert grid.get_zone(25, 10) == ZONE_NONE, "Zone removal failed"
                        Logger.info("[Zone Test] Zone removal successful")
                        
                        # Re-add farm zone
                        zone_manager.mark_zone(25, 10, ZONE_FARM)
                        assert grid.get_zone(25, 10) == ZONE_FARM, "Zone re-addition failed"
                        Logger.info("[Zone Test] Zone re-addition successful")
                
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
