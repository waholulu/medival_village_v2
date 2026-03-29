import pygame
import pygame_gui
import os
import time
import argparse
from src.core.ecs import EntityManager
from src.core.time_manager import TimeManager
from src.core.input_manager import InputManager
from src.core.config_manager import ConfigManager
from src.world.grid import Grid, ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL, ZONE_NONE
from src.world.zone_manager import ZoneManager
from src.world.world_generator import WorldGenerator
from src.systems.render_system import RenderSystem
from src.systems.ui_system import UISystem
from src.systems.action_system import ActionSystem
from src.systems.job_system import JobSystem
from src.systems.ai_system import AISystem
from src.systems.needs_system import NeedsSystem
from src.systems.farming_system import FarmingSystem
from src.systems.routine_system import RoutineSystem
from src.systems.survival_system import SurvivalSystem
from src.systems.building_system import BuildingSystem
from src.components.data_components import (
    PositionComponent, MovementComponent, ActionComponent, InventoryComponent,
    HungerComponent, TirednessComponent, MoodComponent, ColdComponent,
    ItemComponent, CropComponent, ResourceComponent, SleepStateComponent, JobComponent,
)
from src.components.building_components import BlueprintComponent, BuildingComponent
from src.components.skill_component import SkillComponent
from src.components.tags import IsSelectable, IsTree, IsPlayer, IsVillager
from src.utils.logger import Logger, LogCategory
from src.utils.diagnostic_logger import DiagnosticLogger


# ========================= Initialization =========================

def create_core_systems(config_manager: ConfigManager):
    """Create time manager, entity manager, grid, zone manager, and job system."""
    global_conf = config_manager.get("global", {})
    sim_conf = config_manager.get("simulation", {})

    tick_rate = global_conf.get("tick_rate", 60)
    day_length = sim_conf.get("day_length_seconds", 600.0)
    season_length = sim_conf.get("season_length_days", 90)
    starting_season = sim_conf.get("starting_season", "spring")

    time_manager = TimeManager(
        tick_rate=tick_rate, day_length_seconds=day_length,
        season_length_days=season_length, starting_season=starting_season
    )
    Logger.set_time_manager(time_manager)
    entity_manager = EntityManager()

    pixels_per_unit = global_conf.get("pixels_per_unit", 32)
    width = global_conf.get("screen_width", 1280)
    height = global_conf.get("screen_height", 720)
    map_width = max(80, width // pixels_per_unit + 20)
    map_height = max(60, height // pixels_per_unit + 20)
    grid = Grid(map_width, map_height)

    zone_manager = ZoneManager(grid)
    job_system = JobSystem()

    return time_manager, entity_manager, grid, zone_manager, job_system


def create_logic_systems(entity_manager, job_system, grid, zone_manager, config_manager, time_manager):
    """Create all game logic systems."""
    action_system = ActionSystem(entity_manager, grid, config_manager, time_manager)
    ai_system = AISystem(entity_manager, job_system, grid, zone_manager, config_manager, time_manager)
    needs_system = NeedsSystem(entity_manager, time_manager, config_manager)
    farming_system = FarmingSystem(entity_manager, job_system, grid, zone_manager, time_manager, config_manager)
    routine_system = RoutineSystem(entity_manager, time_manager, config_manager)
    survival_system = SurvivalSystem(entity_manager, time_manager, config_manager, grid)
    building_system = BuildingSystem(entity_manager, job_system, grid, config_manager)
    return action_system, ai_system, needs_system, farming_system, routine_system, survival_system, building_system


def create_graphics_systems(config_manager, grid, entity_manager, zone_manager, time_manager):
    """Create screen, UI manager, input, render, and UI systems. Returns None tuple in headless mode."""
    global_conf = config_manager.get("global", {})
    screen_width = global_conf.get("screen_width", 1280)
    screen_height = global_conf.get("screen_height", 720)
    title = global_conf.get("title", "Project Medieval")

    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption(title)

    ui_manager = pygame_gui.UIManager((screen_width, screen_height))
    input_manager = InputManager(ui_manager)
    render_system = RenderSystem(screen, grid, entity_manager, config_manager.config, zone_manager, time_manager)
    ui_system = UISystem(screen, ui_manager, entity_manager)

    Logger.info("Graphical systems initialized")
    return screen, ui_manager, input_manager, render_system, ui_system


# ========================= Event Handling =========================

def handle_events(input_manager, ui_manager, ui_system, render_system, entity_manager, pixels_per_unit):
    """Process all pygame events and update input state."""
    input_manager.camera_move_vector = [0, 0]
    input_manager.zoom_change = 0
    input_manager.time_scale_request = None
    input_manager.last_command = None

    for event in pygame.event.get():
        ui_manager.process_events(event)
        ui_system.handle_ui_event(event)

        if event.type == pygame.QUIT:
            input_manager.should_quit = True
        elif event.type == pygame.KEYDOWN:
            _handle_keydown(event, input_manager)
        elif event.type == pygame.MOUSEWHEEL:
            if not ui_manager.get_hovering_any_element():
                input_manager.zoom_change = event.y
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if not ui_manager.get_hovering_any_element():
                _handle_mouse_click(event, input_manager, render_system, entity_manager, pixels_per_unit)

    # Continuous key state for camera movement
    keys = pygame.key.get_pressed()
    for key, (dx, dy) in input_manager.key_map.items():
        if keys[key]:
            input_manager.camera_move_vector[0] += dx
            input_manager.camera_move_vector[1] += dy


def _handle_keydown(event, input_manager):
    """Handle keyboard press events."""
    if event.key == pygame.K_ESCAPE:
        input_manager.should_quit = True
    elif event.key == pygame.K_SPACE:
        input_manager.is_paused = not input_manager.is_paused
        status = "PAUSED" if input_manager.is_paused else "RESUMED"
        Logger.log(LogCategory.INPUT, f"Game {status}")
    elif event.key == pygame.K_1:
        input_manager.time_scale_request = 1.0
    elif event.key == pygame.K_2:
        input_manager.time_scale_request = 2.0
    elif event.key == pygame.K_3:
        input_manager.time_scale_request = 5.0
    elif event.key == pygame.K_4:
        input_manager.time_scale_request = 10.0
    elif event.key == pygame.K_F5:
        if input_manager.zone_placement_mode == ZONE_STOCKPILE:
            input_manager.zone_placement_mode = None
            Logger.log(LogCategory.INPUT, "Zone placement: OFF")
        else:
            input_manager.zone_placement_mode = ZONE_STOCKPILE
            Logger.log(LogCategory.INPUT, "Zone placement: STOCKPILE (Right-click to place)")
    elif event.key == pygame.K_F6:
        if input_manager.zone_placement_mode == ZONE_FARM:
            input_manager.zone_placement_mode = None
            Logger.log(LogCategory.INPUT, "Zone placement: OFF")
        else:
            input_manager.zone_placement_mode = ZONE_FARM
            Logger.log(LogCategory.INPUT, "Zone placement: FARM (Right-click to place)")
    elif event.key == pygame.K_F7:
        if input_manager.zone_placement_mode == ZONE_RESIDENTIAL:
            input_manager.zone_placement_mode = None
            Logger.log(LogCategory.INPUT, "Zone placement: OFF")
        else:
            input_manager.zone_placement_mode = ZONE_RESIDENTIAL
            Logger.log(LogCategory.INPUT, "Zone placement: RESIDENTIAL (Right-click to place)")
    elif event.key == pygame.K_x:
        input_manager.zone_placement_mode = None
        Logger.log(LogCategory.INPUT, "Zone placement: OFF")


def _handle_mouse_click(event, input_manager, render_system, entity_manager, pixels_per_unit):
    """Handle mouse button click events."""
    if event.button == 3:  # Right Click
        wx, wy = render_system.screen_to_world(event.pos[0], event.pos[1])
        if input_manager.zone_placement_mode is not None:
            input_manager.zone_placement_pos = (wx, wy)
            input_manager.last_command = {
                'type': 'SET_ZONE', 'world_pos': (wx, wy),
                'zone_type': input_manager.zone_placement_mode
            }
        else:
            input_manager.last_command = {'type': 'INTERACT_OR_MOVE', 'world_pos': (wx, wy)}
    elif event.button == 1:  # Left Click
        mx, my = event.pos
        tile_pos = render_system.get_tile_at_screen_pos(mx, my)
        render_system.selected_tile = tile_pos

        selected_id = None
        for e, pos, _ in entity_manager.get_entities_with(PositionComponent, IsSelectable):
            if pos.x == tile_pos[0] and pos.y == tile_pos[1]:
                selected_id = e
                break
        render_system.selected_entity_id = selected_id


# ========================= Command Processing =========================

def process_commands(input_manager, render_system, entity_manager, zone_manager, grid, pixels_per_unit, config_manager):
    """Process queued commands from input."""
    if not input_manager.last_command:
        return

    cmd = input_manager.last_command
    
    if cmd['type'] == 'PLACE_BLUEPRINT':
        wx, wy = cmd['world_pos']
        tx = int(wx / pixels_per_unit)
        ty = int(wy / pixels_per_unit)
        blueprint_type = cmd['blueprint_type']
        
        b_config = config_manager.get(f"entities.buildings.{blueprint_type}", {})
        if not b_config:
            Logger.log(LogCategory.GAMEPLAY, f"Cannot place blueprint: unknown type {blueprint_type}")
            return
            
        cost = b_config.get("cost", {})
        work = b_config.get("work_required", 100.0)
        
        # Check if something is already here
        can_place = True
        for e, pos in entity_manager.get_entities_with(PositionComponent):
            if pos.x == tx and pos.y == ty:
                if entity_manager.has_component(e, BlueprintComponent) or entity_manager.has_component(e, BuildingComponent):
                    can_place = False
                    break
                    
        if can_place:
            blueprint_entity = entity_manager.create_entity()
            entity_manager.add_component(blueprint_entity, PositionComponent(x=tx, y=ty))
            entity_manager.add_component(blueprint_entity, BlueprintComponent(
                building_type=blueprint_type,
                required_materials=cost,
                work_required=work
            ))
            Logger.log(LogCategory.GAMEPLAY, f"Placed {blueprint_type} blueprint at ({tx}, {ty})")
        else:
            Logger.log(LogCategory.GAMEPLAY, f"Cannot place blueprint here.")
        zone_names = {ZONE_STOCKPILE: "Stockpile", ZONE_FARM: "Farm", ZONE_RESIDENTIAL: "Residential"}
        zone_name = zone_names.get(zone_type, "Unknown")
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

    elif cmd['type'] == 'SET_ZONE':
        wx, wy = cmd['world_pos']
        tx = int(wx / pixels_per_unit)
        ty = int(wy / pixels_per_unit)
        zone_type = cmd['zone_type']

        zone_manager.mark_zone(tx, ty, zone_type)
        zone_names = {ZONE_STOCKPILE: "Stockpile", ZONE_FARM: "Farm", ZONE_RESIDENTIAL: "Residential"}
        zone_name = zone_names.get(zone_type, "Unknown")
        Logger.gameplay(f"Placed {zone_name} zone at ({tx}, {ty})")


# ========================= Inspector Panel =========================

def build_inspector_info(render_system, entity_manager, grid, input_manager, pixels_per_unit):
    """Build the inspector info string for the selected tile/entity."""
    if not render_system.selected_tile:
        return "Select a tile..."

    tile_pos = render_system.selected_tile
    selected_id = render_system.selected_entity_id

    zone = grid.get_zone(*tile_pos)
    zone_names = {ZONE_STOCKPILE: "Stockpile", ZONE_FARM: "Farm", ZONE_RESIDENTIAL: "Residential"}
    zone_str = zone_names.get(zone, "None")

    # Zone placement mode indicator
    zone_mode = input_manager.get_zone_placement_mode()
    mode_names = {
        ZONE_STOCKPILE: "\n[Mode: Stockpile Placement - Right-click to place]",
        ZONE_FARM: "\n[Mode: Farm Placement - Right-click to place]",
        ZONE_RESIDENTIAL: "\n[Mode: Residential Placement - Right-click to place]"
    }
    mode_str = mode_names.get(zone_mode, "")

    # Terrain info
    terrain_id = grid.get_terrain(tile_pos[0], tile_pos[1])
    terrain_names = {0: "Grass", 1: "Dirt", 2: "Water", 3: "Stone"}
    terrain_name = terrain_names.get(terrain_id, "Unknown")

    info = f"<b>Tile: ({tile_pos[0]}, {tile_pos[1]})</b>\n"
    info += f"Zone: {zone_str}\n"
    info += f"Terrain: {terrain_name}\n"
    info += f"Walkable: {'Yes' if grid.is_walkable(tile_pos[0], tile_pos[1]) else 'No'}\n"

    if mode_str:
        info += f"\n{mode_str.strip()}\n"

    if selected_id is not None:
        info += _build_entity_info(selected_id, entity_manager)

    return info


def _build_entity_info(entity_id: int, em: EntityManager) -> str:
    """Build detailed info string for a selected entity."""
    info = f"\n<b>=== Entity {entity_id} ===</b>\n"

    # Entity type
    entity_type = "Unknown"
    if em.has_component(entity_id, IsPlayer):
        entity_type = "Villager (Player)"
    elif em.has_component(entity_id, IsVillager):
        entity_type = "Villager"
    elif em.has_component(entity_id, IsTree):
        entity_type = "Tree"
    elif em.has_component(entity_id, ItemComponent):
        entity_type = "Item"
    elif em.has_component(entity_id, CropComponent):
        entity_type = "Crop"
    elif em.has_component(entity_id, BlueprintComponent):
        entity_type = "Blueprint"
    elif em.has_component(entity_id, BuildingComponent):
        entity_type = "Building"
    elif em.has_component(entity_id, ResourceComponent):
        entity_type = "Resource"
    info += f"Type: {entity_type}\n"

    pos = em.get_component(entity_id, PositionComponent)
    if pos:
        info += f"Position: ({pos.x}, {pos.y})\n"

    # Villager-specific info
    if em.has_component(entity_id, IsPlayer) or em.has_component(entity_id, IsVillager):
        info += _build_villager_info(entity_id, em)

    # Resource info
    resource = em.get_component(entity_id, ResourceComponent)
    if resource:
        info += f"\n<b>--- Resource ---</b>\n"
        info += f"Type: {resource.resource_type}\n"
        info += f"Health: {resource.health}/{resource.max_health}\n"
        if resource.drops:
            info += "Drops:\n"
            for drop_type, drop_range in resource.drops.items():
                info += f"  • {drop_type}: {drop_range[0]}-{drop_range[1]}\n"

    # Item info
    item_comp = em.get_component(entity_id, ItemComponent)
    if item_comp:
        info += f"\n<b>--- Item ---</b>\n"
        info += f"Type: {item_comp.item_type}\n"
        info += f"Amount: {item_comp.amount}\n"
        if item_comp.food_value > 0:
            info += f"Food Value: {item_comp.food_value}\n"

    # Crop info
    crop = em.get_component(entity_id, CropComponent)
    if crop:
        info += f"\n<b>--- Crop ---</b>\n"
        info += f"Type: {crop.crop_type}\n"
        info += f"State: {crop.state}\n"
        info += f"Growth: {crop.growth_progress * 100:.1f}%\n"
        if crop.state == "ripe":
            info += "Status: Ready to harvest!\n"
        elif crop.state == "growing":
            remaining = (1.0 - crop.growth_progress) * 100
            info += f"Status: Growing ({remaining:.1f}% remaining)\n"
            
    # Blueprint info
    blueprint = em.get_component(entity_id, BlueprintComponent)
    if blueprint:
        info += f"\n<b>--- Blueprint: {blueprint.building_type} ---</b>\n"
        info += f"Work: {blueprint.work_completed:.1f}/{blueprint.work_required:.1f}\n"
        for mat, req in blueprint.required_materials.items():
             curr = blueprint.current_materials.get(mat, 0)
             info += f"  • {mat}: {curr}/{req}\n"

    # Building info
    building = em.get_component(entity_id, BuildingComponent)
    if building:
        info += f"\n<b>--- Building: {building.building_type} ---</b>\n"
        info += "Status: Completed\n"

    return info


def _build_villager_info(entity_id: int, em: EntityManager) -> str:
    """Build villager-specific status info."""
    info = "\n<b>--- Villager Status ---</b>\n"

    skill_comp = em.get_component(entity_id, SkillComponent)
    if skill_comp and skill_comp.skills:
        info += "Skills:\n"
        for skill_name, skill_level in skill_comp.skills.items():
            info += f"  • {skill_name}: {skill_level * 100:.1f}%\n"

    hunger = em.get_component(entity_id, HungerComponent)
    tiredness = em.get_component(entity_id, TirednessComponent)
    mood = em.get_component(entity_id, MoodComponent)
    if hunger or tiredness or mood:
        info += "Needs:\n"
        if hunger:
            status = "Low" if hunger.hunger < 50 else "Medium" if hunger.hunger < 80 else "High"
            info += f"  • Hunger: {hunger.hunger:.1f}/100 ({status})\n"
        if tiredness:
            status = "Low" if tiredness.tiredness < 50 else "Medium" if tiredness.tiredness < 90 else "High"
            info += f"  • Tiredness: {tiredness.tiredness:.1f}/100 ({status})\n"
        if mood:
            status = "Poor" if mood.mood < 30 else "Fair" if mood.mood < 70 else "Good"
            info += f"  • Mood: {mood.mood:.1f}/100 ({status})\n"

    act = em.get_component(entity_id, ActionComponent)
    if act:
        info += f"Action: {act.current_action}\n"
        if act.target_entity_id:
            info += f"Target Entity: {act.target_entity_id}\n"
        if act.target_pos:
            info += f"Target Pos: {act.target_pos}\n"

    move_comp = em.get_component(entity_id, MovementComponent)
    if move_comp:
        if move_comp.target:
            info += f"Moving to: {move_comp.target}\n"
        if move_comp.path:
            info += f"Path length: {len(move_comp.path)} tiles\n"
        info += f"Speed: {move_comp.speed:.1f}\n"

    job_comp = em.get_component(entity_id, JobComponent)
    if job_comp:
        info += f"Job: {job_comp.job_type} (ID: {job_comp.job_id})\n"
        if job_comp.target_pos:
            info += f"Job Target: {job_comp.target_pos}\n"

    from src.components.data_components import RoutineComponent
    routine = em.get_component(entity_id, RoutineComponent)
    if routine:
        info += f"Routine State: {routine.current_state}\n"
        if routine.next_scheduled_activity:
            info += f"Next Activity: {routine.next_scheduled_activity}\n"

    sleep_state = em.get_component(entity_id, SleepStateComponent)
    if sleep_state:
        info += f"Sleeping: {'Yes' if sleep_state.is_sleeping else 'No'}\n"
        if sleep_state.sleep_location:
            info += f"Sleep Location: {sleep_state.sleep_location}\n"

    inv = em.get_component(entity_id, InventoryComponent)
    if inv:
        info += f"Inventory ({len(inv.items)} types, {sum(inv.items.values())} items):\n"
        if inv.items:
            for item_type, amount in inv.items.items():
                info += f"  • {item_type}: {amount}\n"
        else:
            info += "  (empty)\n"
        info += f"Capacity: {inv.capacity}\n"

    return info


# ========================= Headless Logging =========================

def log_headless_status(time_manager, entity_manager, villagers, job_system, grid):
    """Log detailed simulation status in headless mode."""
    game_time_str = (
        f"Day {time_manager.day} "
        f"{int(time_manager.time_of_day):02d}:{int((time_manager.time_of_day % 1.0) * 60):02d}"
    )
    Logger.info(f"[Headless] Game Time: {game_time_str} | Season: {time_manager.get_season()} | Tick: {time_manager.total_ticks}")

    for i, villager_id in enumerate(villagers):
        v_pos = entity_manager.get_component(villager_id, PositionComponent)
        v_act = entity_manager.get_component(villager_id, ActionComponent)
        v_inv = entity_manager.get_component(villager_id, InventoryComponent)
        v_hunger = entity_manager.get_component(villager_id, HungerComponent)
        v_tired = entity_manager.get_component(villager_id, TirednessComponent)
        v_mood = entity_manager.get_component(villager_id, MoodComponent)
        v_cold = entity_manager.get_component(villager_id, ColdComponent)
        v_job = entity_manager.get_component(villager_id, JobComponent)
        from src.components.data_components import RoutineComponent
        v_routine = entity_manager.get_component(villager_id, RoutineComponent)
        v_skill = entity_manager.get_component(villager_id, SkillComponent)

        needs_str = ""
        if v_hunger: needs_str += f"Hunger:{v_hunger.hunger:.1f} "
        if v_tired: needs_str += f"Tired:{v_tired.tiredness:.1f} "
        if v_mood: needs_str += f"Mood:{v_mood.mood:.1f} "
        if v_cold: needs_str += f"Cold:{v_cold.cold:.1f} "

        job_str = f"Job:{v_job.job_type if v_job else 'None'}"
        routine_str = f"Routine:{v_routine.current_state if v_routine else 'None'}"
        skill_str = ""
        if v_skill:
            skill_str = "Skills:" + ",".join([f"{k}:{v:.2f}" for k, v in v_skill.skills.items()])

        log_msg = (
            f"[Villager {i + 1}] Pos:({v_pos.x},{v_pos.y}) | {needs_str}| {job_str} | "
            f"{routine_str} | Act:{v_act.current_action if v_act else 'None'} | "
            f"Inv:{v_inv.items if v_inv else {}} | {skill_str}"
        )
        Logger.info(log_msg)

    available_jobs = job_system.get_available_jobs()
    Logger.info(f"[JobSystem] Available jobs: {len(available_jobs)} | Types: {[j.job_type for j in available_jobs]}")

    items_on_stockpile = {}
    for e, item, pos in entity_manager.get_entities_with(ItemComponent, PositionComponent):
        zone = grid.get_zone(pos.x, pos.y)
        if zone == ZONE_STOCKPILE:
            items_on_stockpile[item.item_type] = items_on_stockpile.get(item.item_type, 0) + item.amount
    if items_on_stockpile:
        Logger.info(f"[Stockpile] Items: {items_on_stockpile}")

    tree_count = sum(1 for e, _ in entity_manager.get_entities_with(IsTree))
    Logger.info(f"[Resources] Trees remaining: {tree_count}")

    crop_count = 0
    ripe_crops = 0
    for e, crop in entity_manager.get_entities_with(CropComponent):
        crop_count += 1
        if crop.state == "ripe":
            ripe_crops += 1
    if crop_count > 0:
        Logger.info(f"[Farming] Crops: {crop_count} total, {ripe_crops} ripe")


# ========================= Main Entry Point =========================

def quick_check_report(summary_path="logs/villager_summary.txt", detail_path="logs/villager_detail.txt"):
    """Scan diagnostic logs and print a quick health report after a quick-mode run."""
    import re

    print("\n" + "=" * 60)
    print("  QUICK-CHECK REPORT")
    print("=" * 60)

    # --- Read summary log ---
    summary_lines = []
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_lines = f.readlines()

    # --- Read detail log ---
    detail_lines = []
    if os.path.exists(detail_path):
        with open(detail_path, "r", encoding="utf-8") as f:
            detail_lines = f.readlines()

    if not summary_lines and not detail_lines:
        print("  [!] No diagnostic logs found. Something went wrong during init.")
        print("=" * 60)
        return

    # --- Collect issues ---
    errors = []       # Critical problems
    warnings = []     # Concerning but not fatal
    info_items = []   # Interesting observations

    # 1) Check for Python exceptions / tracebacks in detail log
    for i, line in enumerate(detail_lines):
        if "Traceback" in line or "Exception" in line or "Error:" in line:
            errors.append(f"Exception detected in detail log near line {i+1}: {line.strip()[:100]}")

    # 2) Check for critical need alerts (!! markers in summary)
    hunger_crits = 0
    tiredness_crits = 0
    mood_crits = 0
    cold_crits = 0
    for line in summary_lines:
        if "!! HUNGER" in line:
            hunger_crits += 1
        if "!! TIREDNESS" in line:
            tiredness_crits += 1
        if "!! MOOD LOW" in line:
            mood_crits += 1
        if "!! COLD" in line:
            cold_crits += 1

    if hunger_crits:
        warnings.append(f"Hunger critical alerts: {hunger_crits}")
    if tiredness_crits:
        warnings.append(f"Tiredness critical alerts: {tiredness_crits}")
    if mood_crits:
        warnings.append(f"Mood low alerts: {mood_crits}")
    if cold_crits:
        warnings.append(f"Cold critical alerts: {cold_crits}")

    # 3) Check that villagers are actually doing things (not stuck idle)
    # Check both summary (significant changes) and detail (includes idle<->move)
    action_changes_summary = sum(1 for line in summary_lines if "Action:" in line)
    action_changes_detail = sum(1 for line in detail_lines if "Action:" in line)
    routine_changes = sum(1 for line in summary_lines if "Routine:" in line)
    job_events = sum(1 for line in summary_lines if "Job:" in line)

    if action_changes_detail == 0 and action_changes_summary == 0:
        errors.append("No action changes detected — villagers may be completely stuck")
    elif action_changes_summary == 0 and action_changes_detail > 0:
        info_items.append(f"Action changes: {action_changes_detail} (idle/move only — normal early game)")
    elif action_changes_summary < 3:
        warnings.append(f"Very few significant action changes ({action_changes_summary}) — villagers may be mostly idle")
    else:
        info_items.append(f"Action changes: {action_changes_summary} significant, {action_changes_detail} total")

    if routine_changes > 0:
        info_items.append(f"Routine transitions: {routine_changes}")
    else:
        warnings.append("No routine transitions detected")

    if job_events > 0:
        info_items.append(f"Job events: {job_events}")

    # 4) Check snapshots for stuck needs (last snapshot)
    last_snapshot_lines = []
    for i in range(len(summary_lines) - 1, -1, -1):
        if "SNAPSHOT" in summary_lines[i]:
            # Grab snapshot lines until next empty line or end
            for j in range(i + 1, len(summary_lines)):
                if summary_lines[j].strip() == "" or "SNAPSHOT" in summary_lines[j]:
                    break
                last_snapshot_lines.append(summary_lines[j].strip())
            break

    if last_snapshot_lines:
        info_items.append("Last snapshot (final state):")
        for sl in last_snapshot_lines:
            info_items.append(f"  {sl}")

        # Check for villagers with extreme needs in last snapshot
        for sl in last_snapshot_lines:
            match = re.search(r'Hunger:\s*(\d+)', sl)
            if match and int(match.group(1)) >= 80:
                villager_match = re.match(r'(V\d+)', sl)
                vid = villager_match.group(1) if villager_match else "?"
                errors.append(f"{vid} has critical hunger ({match.group(1)}) at end of run")
            match = re.search(r'Tired:\s*(\d+)', sl)
            if match and int(match.group(1)) >= 95:
                villager_match = re.match(r'(V\d+)', sl)
                vid = villager_match.group(1) if villager_match else "?"
                warnings.append(f"{vid} has extreme tiredness ({match.group(1)}) at end of run")

    # 5) Count total snapshots to verify simulation progressed
    snapshot_count = sum(1 for line in summary_lines if "SNAPSHOT" in line)
    if snapshot_count == 0:
        errors.append("No snapshots written — simulation may not have progressed at all")
    elif snapshot_count == 1:
        warnings.append("Only 1 snapshot — simulation barely progressed")
    else:
        info_items.append(f"Total snapshots: {snapshot_count}")

    # --- Print Report ---
    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    [X] {e}")

    if warnings:
        print(f"\n  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"    [!] {w}")

    if not errors and not warnings:
        print("\n  [OK] No errors or warnings detected!")

    if info_items:
        print(f"\n  INFO:")
        for item in info_items:
            print(f"    - {item}")

    total_summary_lines = len(summary_lines)
    total_detail_lines = len(detail_lines)
    print(f"\n  Log sizes: summary={total_summary_lines} lines, detail={total_detail_lines} lines")
    print(f"  Full logs: {os.path.abspath(summary_path)}")
    print(f"             {os.path.abspath(detail_path)}")
    print("=" * 60)

    if errors:
        print("  VERDICT: ISSUES FOUND — check logs for details")
    elif warnings:
        print("  VERDICT: OK with warnings — review if needed")
    else:
        print("  VERDICT: ALL CLEAR")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Project Medieval Game")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no GUI)")
    parser.add_argument("--diagnostic", action="store_true", help="Enable two-tier diagnostic logging to logs/")
    parser.add_argument("--quick", type=float, nargs="?", const=10.0, default=None,
                        metavar="SECONDS",
                        help="Quick-check mode: run headless+diagnostic for N seconds (default 10), then report")
    args = parser.parse_args()

    # --quick implies --headless and --diagnostic
    if args.quick is not None:
        args.headless = True
        args.diagnostic = True

    # Initialization
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()

    config_manager = ConfigManager("config/balance.json")
    global_conf = config_manager.get("global", {})
    pixels_per_unit = global_conf.get("pixels_per_unit", 32)
    tick_rate = global_conf.get("tick_rate", 60)

    # Core systems
    time_manager, entity_manager, grid, zone_manager, job_system = create_core_systems(config_manager)

    # Logic systems
    (action_system, ai_system, needs_system,
     farming_system, routine_system, survival_system, building_system) = create_logic_systems(
        entity_manager, job_system, grid, zone_manager, config_manager, time_manager
    )

    # World generation
    world_gen = WorldGenerator(config_manager, entity_manager, grid, zone_manager, job_system)
    villagers, tree_positions = world_gen.generate_all()

    # Diagnostic logger (optional)
    diag_logger = None
    if args.diagnostic:
        diag_logger = DiagnosticLogger(entity_manager, time_manager)
        diag_logger.start(villagers, config_manager)
        Logger.info("Diagnostic logging enabled -> logs/villager_summary.txt, logs/villager_detail.txt")

    # Graphics systems (conditional)
    screen = ui_manager = input_manager = render_system = ui_system = None
    if not args.headless:
        screen, ui_manager, input_manager, render_system, ui_system = create_graphics_systems(
            config_manager, grid, entity_manager, zone_manager, time_manager
        )
    else:
        Logger.info("Running in Headless Mode (uncapped speed, fixed time step)")
        time_manager.use_fixed_dt = True

    Logger.info("Core systems initialized")
    Logger.info("Game Loop Started")
    if args.quick is not None:
        Logger.info(f"Quick-check mode: will run for {args.quick:.1f} wall-clock seconds (uncapped speed)")

    # Game Loop
    running = True
    clock = pygame.time.Clock()
    quick_start_time = time.time() if args.quick is not None else None

    while running:
        dt = time_manager.get_delta_time()

        if not args.headless:
            # === Graphical Loop ===
            handle_events(input_manager, ui_manager, ui_system, render_system, entity_manager, pixels_per_unit)

            if input_manager.should_quit:
                running = False
                break

            # Pause / time scale
            if input_manager.is_paused != time_manager.is_paused:
                time_manager.toggle_pause()
            if input_manager.time_scale_request is not None:
                time_manager.set_time_scale(input_manager.time_scale_request)

            # Camera
            move_vec = input_manager.get_camera_movement()
            if move_vec[0] != 0 or move_vec[1] != 0:
                camera_speed_multiplier = 1.0 / 60.0
                render_system.move_camera(move_vec[0] * camera_speed_multiplier,
                                          move_vec[1] * camera_speed_multiplier)
            zoom_change = input_manager.get_zoom_change()
            if zoom_change != 0:
                render_system.adjust_zoom(zoom_change)

            # UI
            ui_system.update_villager_panel()

            # Commands
            process_commands(input_manager, render_system, entity_manager, zone_manager, grid, pixels_per_unit, config_manager)

            # Inspector
            info = build_inspector_info(render_system, entity_manager, grid, input_manager, pixels_per_unit)
            ui_system.update_inspector(info)

            # Update logic
            time_manager.update()
            needs_system.update(dt)
            routine_system.update(dt)
            farming_system.update(dt)
            survival_system.update(dt)
            building_system.update(dt)
            ai_system.update(dt)
            action_system.update(dt)

            # Diagnostic logging (after all systems updated)
            if diag_logger:
                diag_logger.detect_changes()

            # Render
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
            # === Headless Loop ===
            pygame.event.pump()
            time_manager.update()
            needs_system.update(dt)
            routine_system.update(dt)
            farming_system.update(dt)
            survival_system.update(dt)
            building_system.update(dt)
            ai_system.update(dt)
            action_system.update(dt)

            # Diagnostic logging (after all systems updated)
            if diag_logger:
                diag_logger.detect_changes()

            if not hasattr(time_manager, '_last_headless_log_tick'):
                time_manager._last_headless_log_tick = 0
            if time_manager.total_ticks - time_manager._last_headless_log_tick >= 360:
                time_manager._last_headless_log_tick = time_manager.total_ticks
                log_headless_status(time_manager, entity_manager, villagers, job_system, grid)

            # Quick-check mode: exit after N real-time seconds
            if quick_start_time is not None:
                elapsed_real = time.time() - quick_start_time
                if elapsed_real >= args.quick:
                    Logger.info(f"Quick-check: {elapsed_real:.1f}s real time elapsed — stopping")
                    Logger.info(
                        f"Final game time: Day {time_manager.day} "
                        f"{int(time_manager.time_of_day):02d}:{int((time_manager.time_of_day % 1.0) * 60):02d}"
                    )
                    break

            target_days = 2
            if time_manager.day >= target_days:
                Logger.info(f"Headless simulation completed: {time_manager.day} days elapsed")
                Logger.info(
                    f"Final game time: Day {time_manager.day} "
                    f"{int(time_manager.time_of_day):02d}:{int((time_manager.time_of_day % 1.0) * 60):02d}"
                )
                break

        if not args.headless:
            clock.tick(tick_rate)

    if diag_logger:
        diag_logger.stop()
        Logger.info("Diagnostic logs written to logs/villager_summary.txt and logs/villager_detail.txt")

    config_manager.stop()
    pygame.quit()
    Logger.info("Game Terminated")

    # Quick-check: print health report
    if args.quick is not None:
        quick_check_report()


if __name__ == "__main__":
    main()
