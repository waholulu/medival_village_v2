"""World generation: terrain, zones, and entity spawning."""
from src.core.ecs import EntityManager
from src.core.config_manager import ConfigManager
from src.world.grid import Grid, TERRAIN_WATER, TERRAIN_STONE, TERRAIN_DIRT, ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL
from src.world.zone_manager import ZoneManager
from src.systems.job_system import JobSystem, Job
from src.components.data_components import (
    PositionComponent, MovementComponent, ActionComponent, ResourceComponent,
    InventoryComponent, HungerComponent, TirednessComponent, MoodComponent,
    RoutineComponent, ItemComponent, CropComponent, ColdComponent
)
from src.components.skill_component import SkillComponent
from src.components.tags import IsWalkable, IsTree, IsSelectable, IsPlayer, IsVillager
from src.utils.logger import Logger
from typing import List, Tuple


class WorldGenerator:
    """Handles terrain generation, zone setup, and initial entity spawning."""

    def __init__(self, config_manager: ConfigManager, entity_manager: EntityManager,
                 grid: Grid, zone_manager: ZoneManager, job_system: JobSystem):
        self.config_manager = config_manager
        self.entity_manager = entity_manager
        self.grid = grid
        self.zone_manager = zone_manager
        self.job_system = job_system

    def generate_terrain(self) -> None:
        """Generate the terrain layout: river, farmland, stone quarry."""
        map_width = self.grid.width
        map_height = self.grid.height

        # River on the east side
        river_x = map_width - 8
        for y in range(5, map_height - 5):
            self.grid.set_terrain(river_x, y, TERRAIN_WATER)
            if y % 3 == 0 and river_x + 1 < map_width:
                self.grid.set_terrain(river_x + 1, y, TERRAIN_WATER)

        # Farmland area (south, dirt terrain)
        farm_start_y = map_height // 2 + 5
        for x in range(10, map_width - 15):
            for y in range(farm_start_y, map_height - 5):
                self.grid.set_terrain(x, y, TERRAIN_DIRT)

        # Stone quarry area (west)
        for x in range(2, 8):
            for y in range(10, 20):
                if (x + y) % 3 == 0:
                    self.grid.set_terrain(x, y, TERRAIN_STONE)

        Logger.info(f"Generated terrain: {map_width}x{map_height} tiles")

    def setup_zones(self) -> dict:
        """Create stockpile, farm, and residential zones. Returns zone center positions."""
        map_width = self.grid.width
        map_height = self.grid.height
        village_center_x = map_width // 2
        village_center_y = map_height // 2

        positions = {}

        # Stockpile Zone
        stockpile_size = 4
        sx = village_center_x - stockpile_size // 2
        sy = village_center_y - stockpile_size // 2
        for x in range(sx, sx + stockpile_size):
            for y in range(sy, sy + stockpile_size):
                if 0 <= x < map_width and 0 <= y < map_height:
                    self.zone_manager.mark_zone(x, y, ZONE_STOCKPILE)
        positions['stockpile'] = (sx + stockpile_size // 2, sy + stockpile_size // 2)
        Logger.info(f"Created Stockpile zone at {sx}-{sx + stockpile_size}, {sy}-{sy + stockpile_size}")

        # Farm Zone
        farm_size_x, farm_size_y = 8, 6
        fx = village_center_x - farm_size_x // 2
        fy = map_height // 2 + 8
        for x in range(fx, fx + farm_size_x):
            for y in range(fy, fy + farm_size_y):
                if 0 <= x < map_width and 0 <= y < map_height:
                    self.zone_manager.mark_zone(x, y, ZONE_FARM)
        positions['farm'] = (fx + farm_size_x // 2, fy + farm_size_y // 2)
        positions['farm_start'] = (fx, fy)
        Logger.info(f"Created Farm zone at {fx}-{fx + farm_size_x}, {fy}-{fy + farm_size_y}")

        # Residential Zone
        res_size = 5
        rx = village_center_x - res_size // 2
        ry = village_center_y - res_size - 3
        for x in range(rx, rx + res_size):
            for y in range(ry, ry + res_size):
                if 0 <= x < map_width and 0 <= y < map_height:
                    self.zone_manager.mark_zone(x, y, ZONE_RESIDENTIAL)
        positions['residential'] = (rx + res_size // 2, ry + res_size // 2)
        Logger.info(f"Created Residential zone at {rx}-{rx + res_size}, {ry}-{ry + res_size}")

        return positions

    def spawn_villagers(self, zone_positions: dict) -> List[int]:
        """Spawn villagers near the village center. Returns list of villager entity IDs."""
        village_center_x = self.grid.width // 2
        village_center_y = self.grid.height // 2
        pixels_per_unit = self.config_manager.get("global.pixels_per_unit", 32)
        villager_move_speed_px = self.config_manager.get("entities.villager.move_speed", 50.0)
        villager_move_speed_tiles = villager_move_speed_px / pixels_per_unit

        villager_positions = [
            (village_center_x - 2, village_center_y),
            (village_center_x + 2, village_center_y),
            (village_center_x, village_center_y - 2),
        ]

        villagers: List[int] = []
        for i, (vx, vy) in enumerate(villager_positions):
            villager = self.entity_manager.create_entity()
            self.entity_manager.add_component(villager, PositionComponent(vx, vy))
            self.entity_manager.add_component(villager, MovementComponent(speed=villager_move_speed_tiles))
            self.entity_manager.add_component(villager, ActionComponent())

            if i == 0:
                skills = {"logging": 0.6, "farming": 0.2}
            elif i == 1:
                skills = {"logging": 0.2, "farming": 0.6}
            else:
                skills = self.config_manager.get("entities.villager.default_skills",
                                                  {"logging": 0.1, "farming": 0.1})

            self.entity_manager.add_component(villager, SkillComponent(skills=skills))
            self.entity_manager.add_component(villager, InventoryComponent(capacity=10))
            self.entity_manager.add_component(villager, HungerComponent(hunger=30.0 + i * 5.0))
            self.entity_manager.add_component(villager, TirednessComponent(tiredness=15.0 + i * 3.0))
            self.entity_manager.add_component(villager, MoodComponent(mood=65.0 + i * 5.0))
            self.entity_manager.add_component(villager, ColdComponent(cold=10.0 + i * 2.0))
            self.entity_manager.add_component(villager, RoutineComponent())
            self.entity_manager.add_component(villager, IsSelectable())
            self.entity_manager.add_component(villager, IsWalkable())
            self.entity_manager.add_component(villager, IsVillager())

            if i == 0:
                self.entity_manager.add_component(villager, IsPlayer())

            villagers.append(villager)
            Logger.info(f"Created Villager {i + 1} at ({vx}, {vy}) with skills: {skills}")

        return villagers

    def spawn_resources(self) -> List[Tuple[int, int]]:
        """Spawn trees in forest area. Returns tree positions."""
        tree_positions: List[Tuple[int, int]] = []
        forest_start_x, forest_start_y = 15, 5
        forest_width, forest_height = 25, 15

        for x in range(forest_start_x, forest_start_x + forest_width, 3):
            for y in range(forest_start_y, forest_start_y + forest_height, 3):
                if self.grid.is_walkable(x, y) and (x, y) not in tree_positions:
                    tree = self.entity_manager.create_entity()
                    self.entity_manager.add_component(tree, PositionComponent(x, y))
                    self.entity_manager.add_component(tree, ResourceComponent(
                        resource_type="tree_oak",
                        health=self.config_manager.get("entities.tree_oak.hp", 20),
                        max_health=self.config_manager.get("entities.tree_oak.hp", 20)
                    ))
                    self.entity_manager.add_component(tree, IsTree())
                    self.entity_manager.add_component(tree, IsSelectable())
                    tree_positions.append((x, y))

        Logger.info(f"Created {len(tree_positions)} trees in forest area")

        # Create initial chop jobs for some trees
        for tx, ty in tree_positions[:5]:
            tree_entity = None
            for e, pos in self.entity_manager.get_entities_with(PositionComponent):
                if pos.x == tx and pos.y == ty:
                    tree_entity = e
                    break
            if tree_entity:
                self.job_system.add_job(Job(
                    job_type="chop",
                    target_pos=(tx, ty),
                    target_entity_id=tree_entity,
                    required_skill="logging",
                    priority=4
                ))

        return tree_positions

    def spawn_items(self, zone_positions: dict) -> None:
        """Spawn initial food items and seeds."""
        village_center_x = self.grid.width // 2
        village_center_y = self.grid.height // 2

        # Food items near village center (enough for ~1 day survival)
        food_positions = [
            (village_center_x - 1, village_center_y + 1),
            (village_center_x + 1, village_center_y + 1),
            (village_center_x, village_center_y + 2),
            (village_center_x, village_center_y + 1),
        ]
        for fx, fy in food_positions:
            food_entity = self.entity_manager.create_entity()
            self.entity_manager.add_component(food_entity, PositionComponent(fx, fy))
            self.entity_manager.add_component(food_entity, ItemComponent(
                item_type="food_wheat", amount=3, food_value=30.0
            ))

        # Seeds near farm area
        farm_start = zone_positions.get('farm_start', (30, 40))
        seed_positions = [
            (farm_start[0] + 1, farm_start[1] + 1),
            (farm_start[0] + 2, farm_start[1] + 1),
            (farm_start[0] + 3, farm_start[1] + 1),
        ]
        for sx, sy in seed_positions:
            seed_entity = self.entity_manager.create_entity()
            self.entity_manager.add_component(seed_entity, PositionComponent(sx, sy))
            self.entity_manager.add_component(seed_entity, ItemComponent(
                item_type="seed_wheat", amount=3
            ))

        Logger.info(f"Created {len(food_positions)} food piles and {len(seed_positions)} seed piles")

    def spawn_initial_crops(self, zone_positions: dict) -> None:
        """Spawn a few already-growing crops for testing harvest."""
        farm_start = zone_positions.get('farm_start', (30, 40))
        crop_positions = [
            (farm_start[0] + 1, farm_start[1] + 3),
            (farm_start[0] + 2, farm_start[1] + 3),
            (farm_start[0] + 3, farm_start[1] + 3),
            (farm_start[0] + 4, farm_start[1] + 3),
        ]
        for cx, cy in crop_positions:
            crop_entity = self.entity_manager.create_entity()
            self.entity_manager.add_component(crop_entity, PositionComponent(cx, cy))
            self.entity_manager.add_component(crop_entity, CropComponent(
                crop_type="wheat", growth_progress=0.85, state="growing"
            ))

        Logger.info(f"Created {len(crop_positions)} growing crops in farm zone")

    def generate_all(self) -> Tuple[List[int], List[Tuple[int, int]]]:
        """Run full world generation. Returns (villager_ids, tree_positions)."""
        self.generate_terrain()
        zone_positions = self.setup_zones()
        villagers = self.spawn_villagers(zone_positions)
        tree_positions = self.spawn_resources()
        self.spawn_items(zone_positions)
        self.spawn_initial_crops(zone_positions)

        Logger.info("=== Initial Map Setup Complete ===")
        Logger.info(f"Map Size: {self.grid.width}x{self.grid.height}")
        Logger.info(f"Villagers: {len(villagers)}")
        Logger.info(f"Trees: {len(tree_positions)}")
        Logger.info(f"Zones: Stockpile, Farm, Residential")

        return villagers, tree_positions
