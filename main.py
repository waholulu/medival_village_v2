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
from src.world.grid import Grid, TERRAIN_WATER, TERRAIN_STONE, TERRAIN_GRASS, TERRAIN_DIRT, ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL, ZONE_NONE
from src.world.zone_manager import ZoneManager
from src.systems.render_system import RenderSystem
from src.systems.ui_system import UISystem
from src.systems.action_system import ActionSystem
from src.systems.job_system import JobSystem, Job
from src.systems.ai_system import AISystem
from src.systems.needs_system import NeedsSystem
from src.systems.farming_system import FarmingSystem
from src.systems.routine_system import RoutineSystem
from src.systems.survival_system import SurvivalSystem
from src.components.data_components import PositionComponent, MovementComponent, ActionComponent, ResourceComponent, InventoryComponent, HungerComponent, TirednessComponent, MoodComponent, RoutineComponent, ItemComponent, CropComponent, SleepStateComponent, JobComponent, ColdComponent
from src.components.skill_component import SkillComponent
from src.components.tags import IsWalkable, IsTree, IsSelectable, IsPlayer, IsVillager
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
    
    # World Generation - Realistic Medieval Village Layout
    pixels_per_unit = global_conf.get("pixels_per_unit", 32)
    width = global_conf.get("screen_width", 1280)
    height = global_conf.get("screen_height", 720)
    # Create a larger map for a more realistic village
    map_width = max(80, width // pixels_per_unit + 20)  # At least 80 tiles wide
    map_height = max(60, height // pixels_per_unit + 20)  # At least 60 tiles tall
    grid = Grid(map_width, map_height)
    
    # ===== TERRAIN GENERATION =====
    # Create a realistic terrain layout
    # Center: Village area (grass)
    # North: Forest area (grass with trees)
    # South: Farmland (dirt)
    # East: River/Water source
    # West: Stone quarry area
    
    # 1. Create a river flowing from north to south on the east side
    river_x = map_width - 8
    for y in range(5, map_height - 5):
        grid.set_terrain(river_x, y, TERRAIN_WATER)
        if y % 3 == 0:  # Make river slightly wider in some places
            if river_x + 1 < map_width:
                grid.set_terrain(river_x + 1, y, TERRAIN_WATER)
    
    # 2. Create farmland area (south, dirt terrain)
    farm_start_y = map_height // 2 + 5
    for x in range(10, map_width - 15):
        for y in range(farm_start_y, map_height - 5):
            grid.set_terrain(x, y, TERRAIN_DIRT)
    
    # 3. Create stone quarry area (west)
    for x in range(2, 8):
        for y in range(10, 20):
            if (x + y) % 3 == 0:  # Sparse stone patches
                grid.set_terrain(x, y, TERRAIN_STONE)
    
    # Rest is grass (default)
    Logger.info(f"Generated map: {map_width}x{map_height} tiles")
    
    # New Phase 3 Managers
    zone_manager = ZoneManager(grid)
    job_system = JobSystem()
    
    # Systems
    action_system = ActionSystem(entity_manager, grid, config_manager)
    ai_system = AISystem(entity_manager, job_system, grid, zone_manager, config_manager)
    needs_system = NeedsSystem(entity_manager, time_manager, config_manager)
    farming_system = FarmingSystem(entity_manager, job_system, grid, zone_manager, time_manager, config_manager)
    routine_system = RoutineSystem(entity_manager, time_manager, config_manager)
    survival_system = SurvivalSystem(entity_manager, time_manager, config_manager, grid)

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

    # ===== ZONE SETUP =====
    # Village center coordinates
    village_center_x = map_width // 2
    village_center_y = map_height // 2
    
    # 1. Stockpile Zone (Warehouse area) - Center of village
    stockpile_size = 4
    stockpile_start_x = village_center_x - stockpile_size // 2
    stockpile_start_y = village_center_y - stockpile_size // 2
    for x in range(stockpile_start_x, stockpile_start_x + stockpile_size):
        for y in range(stockpile_start_y, stockpile_start_y + stockpile_size):
            if 0 <= x < map_width and 0 <= y < map_height:
                zone_manager.mark_zone(x, y, ZONE_STOCKPILE)
    stockpile_pos = (stockpile_start_x + stockpile_size // 2, stockpile_start_y + stockpile_size // 2)
    Logger.info(f"Created Stockpile zone at {stockpile_start_x}-{stockpile_start_x + stockpile_size}, {stockpile_start_y}-{stockpile_start_y + stockpile_size}")
    
    # 2. Farm Zone - South area, near farmland
    farm_size_x, farm_size_y = 8, 6
    farm_start_x = village_center_x - farm_size_x // 2
    farm_start_y = map_height // 2 + 8
    for x in range(farm_start_x, farm_start_x + farm_size_x):
        for y in range(farm_start_y, farm_start_y + farm_size_y):
            if 0 <= x < map_width and 0 <= y < map_height:
                zone_manager.mark_zone(x, y, ZONE_FARM)
    farm_pos = (farm_start_x + farm_size_x // 2, farm_start_y + farm_size_y // 2)
    Logger.info(f"Created Farm zone at {farm_start_x}-{farm_start_x + farm_size_x}, {farm_start_y}-{farm_start_y + farm_size_y}")
    
    # 3. Residential Zone - North of village center
    residential_size = 5
    residential_start_x = village_center_x - residential_size // 2
    residential_start_y = village_center_y - residential_size - 3
    for x in range(residential_start_x, residential_start_x + residential_size):
        for y in range(residential_start_y, residential_start_y + residential_size):
            if 0 <= x < map_width and 0 <= y < map_height:
                zone_manager.mark_zone(x, y, ZONE_RESIDENTIAL)
    residential_pos = (residential_start_x + residential_size // 2, residential_start_y + residential_size // 2)
    Logger.info(f"Created Residential zone at {residential_start_x}-{residential_start_x + residential_size}, {residential_start_y}-{residential_start_y + residential_size}")
    
    # ===== SPAWN ENTITIES =====
    # Spawn multiple villagers with different skills
    villagers = []
    villager_positions = [
        (village_center_x - 2, village_center_y),      # Villager 1: Logger (high logging skill)
        (village_center_x + 2, village_center_y),      # Villager 2: Farmer (high farming skill)
        (village_center_x, village_center_y - 2),      # Villager 3: Balanced
    ]
    
    for i, (vx, vy) in enumerate(villager_positions):
        villager = entity_manager.create_entity()
        entity_manager.add_component(villager, PositionComponent(vx, vy))
        entity_manager.add_component(villager, MovementComponent(speed=config_manager.get("entities.villager.move_speed", 50.0)))
        entity_manager.add_component(villager, ActionComponent())
        
        # Different skill distributions
        if i == 0:  # Logger
            skills = {"logging": 0.6, "farming": 0.2}
        elif i == 1:  # Farmer
            skills = {"logging": 0.2, "farming": 0.6}
        else:  # Balanced
            skills = config_manager.get("entities.villager.default_skills", {"logging": 0.1, "farming": 0.1})
        
        entity_manager.add_component(villager, SkillComponent(skills=skills))
        entity_manager.add_component(villager, InventoryComponent(capacity=10))
        entity_manager.add_component(villager, HungerComponent(hunger=30.0 + i * 5.0))  # Varying hunger
        entity_manager.add_component(villager, TirednessComponent(tiredness=15.0 + i * 3.0))  # Varying tiredness
        entity_manager.add_component(villager, MoodComponent(mood=65.0 + i * 5.0))  # Varying mood
        entity_manager.add_component(villager, ColdComponent(cold=10.0 + i * 2.0))  # Varying cold
        entity_manager.add_component(villager, RoutineComponent())
        entity_manager.add_component(villager, IsSelectable())
        entity_manager.add_component(villager, IsWalkable())
        entity_manager.add_component(villager, IsVillager())  # All villagers get this tag
        
        # First villager is the player-selectable one
        if i == 0:
            entity_manager.add_component(villager, IsPlayer())
        
        villagers.append(villager)
        Logger.info(f"Created Villager {i+1} at ({vx}, {vy}) with skills: {skills}")
    
    # ===== SPAWN RESOURCES =====
    # Spawn trees in forest area (north)
    tree_positions = []
    forest_start_x = 15
    forest_start_y = 5
    forest_width = 25
    forest_height = 15
    
    # Create a small forest cluster
    for x in range(forest_start_x, forest_start_x + forest_width, 3):
        for y in range(forest_start_y, forest_start_y + forest_height, 3):
            if grid.is_walkable(x, y) and (x, y) not in tree_positions:
                tree = entity_manager.create_entity()
                entity_manager.add_component(tree, PositionComponent(x, y))
                entity_manager.add_component(tree, ResourceComponent(
                    resource_type="tree_oak",
                    health=config_manager.get("entities.tree_oak.hp", 20),
                    max_health=config_manager.get("entities.tree_oak.hp", 20)
                ))
                entity_manager.add_component(tree, IsTree())
                entity_manager.add_component(tree, IsSelectable())
                tree_positions.append((x, y))
    
    Logger.info(f"Created {len(tree_positions)} trees in forest area")
    
    # Create initial chop jobs for some trees
    for i, (tx, ty) in enumerate(tree_positions[:5]):  # First 5 trees get jobs
        tree_entity = None
        for e, pos in entity_manager.get_entities_with(PositionComponent):
            if pos.x == tx and pos.y == ty:
                tree_entity = e
                break
        if tree_entity:
            chop_job = Job(
                job_type="chop",
                target_pos=(tx, ty),
                target_entity_id=tree_entity,
                required_skill="logging"
            )
            job_system.add_job(chop_job)
    
    # ===== SPAWN ITEMS =====
    # Initial food items near village center
    food_positions = [
        (village_center_x - 1, village_center_y + 1),
        (village_center_x + 1, village_center_y + 1),
        (village_center_x, village_center_y + 2),
    ]
    for fx, fy in food_positions:
        food_entity = entity_manager.create_entity()
        entity_manager.add_component(food_entity, PositionComponent(fx, fy))
        entity_manager.add_component(food_entity, ItemComponent(
            item_type="food_wheat",
            amount=2,
            food_value=30.0
        ))
    
    # Seeds near farm area
    seed_positions = [
        (farm_start_x + 1, farm_start_y + 1),
        (farm_start_x + 2, farm_start_y + 1),
        (farm_start_x + 3, farm_start_y + 1),
    ]
    for sx, sy in seed_positions:
        seed_entity = entity_manager.create_entity()
        entity_manager.add_component(seed_entity, PositionComponent(sx, sy))
        entity_manager.add_component(seed_entity, ItemComponent(
            item_type="seed_wheat",
            amount=3
        ))
    
    Logger.info(f"Created {len(food_positions)} food items and {len(seed_positions)} seed items")
    
    # ===== SPAWN INITIAL CROPS (for testing harvest) =====
    # Plant a few crops that are already growing in the farm zone
    crop_positions = [
        (farm_start_x + 1, farm_start_y + 3),
        (farm_start_x + 2, farm_start_y + 3),
    ]
    for cx, cy in crop_positions:
        crop_entity = entity_manager.create_entity()
        entity_manager.add_component(crop_entity, PositionComponent(cx, cy))
        entity_manager.add_component(crop_entity, CropComponent(
            crop_type="wheat",
            growth_progress=0.7,  # Already 70% grown
            state="growing"
        ))
    
    Logger.info(f"Created {len(crop_positions)} growing crops in farm zone")
    
    Logger.info("=== Initial Map Setup Complete ===")
    Logger.info(f"Map Size: {map_width}x{map_height}")
    Logger.info(f"Villagers: {len(villagers)}")
    Logger.info(f"Trees: {len(tree_positions)}")
    Logger.info(f"Zones: Stockpile, Farm, Residential")
    
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
                    
                    # Build detailed info string
                    info = f"<b>Tile: ({tile_pos[0]}, {tile_pos[1]})</b>\n"
                    info += f"Zone: {zone_str}\n"
                    
                    # Terrain info
                    terrain_id = grid.get_terrain(tile_pos[0], tile_pos[1])
                    terrain_names = {0: "Grass", 1: "Dirt", 2: "Water", 3: "Stone"}
                    terrain_name = terrain_names.get(terrain_id, "Unknown")
                    info += f"Terrain: {terrain_name}\n"
                    info += f"Walkable: {'Yes' if grid.is_walkable(tile_pos[0], tile_pos[1]) else 'No'}\n"
                    
                    if mode_str:
                        info += f"\n{mode_str.strip()}\n"
                    
                    if selected_id is not None:
                        info += f"\n<b>=== Entity {selected_id} ===</b>\n"
                        
                        # Entity type identification
                        entity_type = "Unknown"
                        if entity_manager.has_component(selected_id, IsPlayer):
                            entity_type = "Villager (Player)"
                        elif entity_manager.has_component(selected_id, IsTree):
                            entity_type = "Tree"
                        else:
                            # Check for other component types
                            if entity_manager.has_component(selected_id, ItemComponent):
                                entity_type = "Item"
                            elif entity_manager.has_component(selected_id, CropComponent):
                                entity_type = "Crop"
                            elif entity_manager.has_component(selected_id, ResourceComponent):
                                entity_type = "Resource"
                        info += f"Type: {entity_type}\n"
                        
                        # Position
                        pos = entity_manager.get_component(selected_id, PositionComponent)
                        if pos:
                            info += f"Position: ({pos.x}, {pos.y})\n"
                        
                        # === VILLAGER INFO ===
                        if entity_manager.has_component(selected_id, IsPlayer) or entity_manager.has_component(selected_id, HungerComponent):
                            info += "\n<b>--- Villager Status ---</b>\n"
                            
                            # Skills
                            skill_comp = entity_manager.get_component(selected_id, SkillComponent)
                            if skill_comp and skill_comp.skills:
                                info += "Skills:\n"
                                for skill_name, skill_level in skill_comp.skills.items():
                                    info += f"  • {skill_name}: {skill_level*100:.1f}%\n"
                            
                            # Needs
                            hunger = entity_manager.get_component(selected_id, HungerComponent)
                            tiredness = entity_manager.get_component(selected_id, TirednessComponent)
                            mood = entity_manager.get_component(selected_id, MoodComponent)
                            if hunger or tiredness or mood:
                                info += "Needs:\n"
                                if hunger:
                                    hunger_status = "Low" if hunger.hunger < 50 else "Medium" if hunger.hunger < 80 else "High"
                                    info += f"  • Hunger: {hunger.hunger:.1f}/100 ({hunger_status})\n"
                                if tiredness:
                                    tired_status = "Low" if tiredness.tiredness < 50 else "Medium" if tiredness.tiredness < 90 else "High"
                                    info += f"  • Tiredness: {tiredness.tiredness:.1f}/100 ({tired_status})\n"
                                if mood:
                                    mood_status = "Poor" if mood.mood < 30 else "Fair" if mood.mood < 70 else "Good"
                                    info += f"  • Mood: {mood.mood:.1f}/100 ({mood_status})\n"
                            
                            # Action & Movement
                            act = entity_manager.get_component(selected_id, ActionComponent)
                            if act:
                                info += f"Action: {act.current_action}\n"
                                if act.target_entity_id:
                                    info += f"Target Entity: {act.target_entity_id}\n"
                                if act.target_pos:
                                    info += f"Target Pos: {act.target_pos}\n"
                            
                            move_comp = entity_manager.get_component(selected_id, MovementComponent)
                            if move_comp:
                                if move_comp.target:
                                    info += f"Moving to: {move_comp.target}\n"
                                if move_comp.path:
                                    info += f"Path length: {len(move_comp.path)} tiles\n"
                                info += f"Speed: {move_comp.speed:.1f}\n"
                            
                            # Job
                            job_comp = entity_manager.get_component(selected_id, JobComponent)
                            if job_comp:
                                info += f"Job: {job_comp.job_type} (ID: {job_comp.job_id})\n"
                                if job_comp.target_pos:
                                    info += f"Job Target: {job_comp.target_pos}\n"
                            
                            # Routine
                            routine = entity_manager.get_component(selected_id, RoutineComponent)
                            if routine:
                                info += f"Routine State: {routine.current_state}\n"
                                if routine.next_scheduled_activity:
                                    info += f"Next Activity: {routine.next_scheduled_activity}\n"
                            
                            # Sleep state
                            sleep_state = entity_manager.get_component(selected_id, SleepStateComponent)
                            if sleep_state:
                                info += f"Sleeping: {'Yes' if sleep_state.is_sleeping else 'No'}\n"
                                if sleep_state.sleep_location:
                                    info += f"Sleep Location: {sleep_state.sleep_location}\n"
                            
                            # Inventory
                            inv = entity_manager.get_component(selected_id, InventoryComponent)
                            if inv:
                                info += f"Inventory ({len(inv.items)} types, {sum(inv.items.values())} items):\n"
                                if inv.items:
                                    for item_type, amount in inv.items.items():
                                        info += f"  • {item_type}: {amount}\n"
                                else:
                                    info += "  (empty)\n"
                                info += f"Capacity: {inv.capacity}\n"
                        
                        # === TREE/RESOURCE INFO ===
                        resource = entity_manager.get_component(selected_id, ResourceComponent)
                        if resource:
                            info += "\n<b>--- Resource ---</b>\n"
                            info += f"Type: {resource.resource_type}\n"
                            info += f"Health: {resource.health}/{resource.max_health}\n"
                            if resource.drops:
                                info += "Drops:\n"
                                for drop_type, drop_range in resource.drops.items():
                                    info += f"  • {drop_type}: {drop_range[0]}-{drop_range[1]}\n"
                        
                        # === ITEM INFO ===
                        item_comp = entity_manager.get_component(selected_id, ItemComponent)
                        if item_comp:
                            info += "\n<b>--- Item ---</b>\n"
                            info += f"Type: {item_comp.item_type}\n"
                            info += f"Amount: {item_comp.amount}\n"
                            if item_comp.food_value > 0:
                                info += f"Food Value: {item_comp.food_value}\n"
                        
                        # === CROP INFO ===
                        crop = entity_manager.get_component(selected_id, CropComponent)
                        if crop:
                            info += "\n<b>--- Crop ---</b>\n"
                            info += f"Type: {crop.crop_type}\n"
                            info += f"State: {crop.state}\n"
                            info += f"Growth: {crop.growth_progress*100:.1f}%\n"
                            if crop.state == "ripe":
                                info += "Status: Ready to harvest!\n"
                            elif crop.state == "growing":
                                remaining = (1.0 - crop.growth_progress) * 100
                                info += f"Status: Growing ({remaining:.1f}% remaining)\n"
                        
                    ui_system.update_inspector(info)

            time_manager.update()
            
            # Update Logic Systems
            needs_system.update(dt)
            routine_system.update(dt)
            farming_system.update(dt)
            survival_system.update(dt)
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
            survival_system.update(dt)
            ai_system.update(dt)
            action_system.update(dt)
            
            # Logging (Every ~1 second)
            if time_manager.frame_count % 60 == 0:
                # Log game time and day
                game_time_str = f"Day {time_manager.day} {int(time_manager.time_of_day):02d}:{int((time_manager.time_of_day % 1.0) * 60):02d}"
                Logger.info(f"[Headless] Game Time: {game_time_str} | Season: {time_manager.get_season()} | Tick: {time_manager.total_ticks}")
                
                # Log all villagers' status
                for i, villager_id in enumerate(villagers):
                    v_pos = entity_manager.get_component(villager_id, PositionComponent)
                    v_act = entity_manager.get_component(villager_id, ActionComponent)
                    v_inv = entity_manager.get_component(villager_id, InventoryComponent)
                    v_hunger = entity_manager.get_component(villager_id, HungerComponent)
                    v_tired = entity_manager.get_component(villager_id, TirednessComponent)
                    v_mood = entity_manager.get_component(villager_id, MoodComponent)
                    v_cold = entity_manager.get_component(villager_id, ColdComponent)
                    v_job = entity_manager.get_component(villager_id, JobComponent)
                    v_routine = entity_manager.get_component(villager_id, RoutineComponent)
                    v_skill = entity_manager.get_component(villager_id, SkillComponent)
                    
                    needs_str = ""
                    if v_hunger:
                        needs_str += f"Hunger:{v_hunger.hunger:.1f} "
                    if v_tired:
                        needs_str += f"Tired:{v_tired.tiredness:.1f} "
                    if v_mood:
                        needs_str += f"Mood:{v_mood.mood:.1f} "
                    if v_cold:
                        needs_str += f"Cold:{v_cold.cold:.1f} "
                    
                    job_str = f"Job:{v_job.job_type if v_job else 'None'}"
                    routine_str = f"Routine:{v_routine.current_state if v_routine else 'None'}"
                    skill_str = ""
                    if v_skill:
                        skill_str = "Skills:" + ",".join([f"{k}:{v:.2f}" for k, v in v_skill.skills.items()])
                    
                    log_msg = f"[Villager {i+1}] Pos:({v_pos.x},{v_pos.y}) | {needs_str}| {job_str} | {routine_str} | Act:{v_act.current_action if v_act else 'None'} | Inv:{v_inv.items if v_inv else {}} | {skill_str}"
                    Logger.info(log_msg)
                
                # Log job system status
                available_jobs = job_system.get_available_jobs()
                Logger.info(f"[JobSystem] Available jobs: {len(available_jobs)} | Types: {[j.job_type for j in available_jobs]}")
                
                # Log items on stockpile
                items_on_stockpile = {}
                for e, item, pos in entity_manager.get_entities_with(ItemComponent, PositionComponent):
                    zone = grid.get_zone(pos.x, pos.y)
                    if zone == ZONE_STOCKPILE:
                        items_on_stockpile[item.item_type] = items_on_stockpile.get(item.item_type, 0) + item.amount
                if items_on_stockpile:
                    Logger.info(f"[Stockpile] Items: {items_on_stockpile}")
                
                # Log trees remaining
                tree_count = sum(1 for e, _ in entity_manager.get_entities_with(IsTree))
                Logger.info(f"[Resources] Trees remaining: {tree_count}")
                
                # Log crops status
                crop_count = 0
                ripe_crops = 0
                for e, crop in entity_manager.get_entities_with(CropComponent):
                    crop_count += 1
                    if crop.state == "ripe":
                        ripe_crops += 1
                if crop_count > 0:
                    Logger.info(f"[Farming] Crops: {crop_count} total, {ripe_crops} ripe")

            # Exit condition: Run for 2 game days
            target_days = 2
            if time_manager.day >= target_days:
                Logger.info(f"Headless simulation completed: {time_manager.day} days elapsed")
                Logger.info(f"Final game time: Day {time_manager.day} {int(time_manager.time_of_day):02d}:{int((time_manager.time_of_day % 1.0) * 60):02d}")
                break
                
        clock.tick(tick_rate)

    config_manager.stop()
    pygame.quit()
    Logger.info("Game Terminated")

if __name__ == "__main__":
    main()
