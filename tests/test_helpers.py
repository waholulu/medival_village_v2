"""
测试辅助函数
提供创建测试世界、村民等常用功能

所有测试都在headless模式下运行，不创建任何UI组件。
"""
import os
import sys
import pygame

# 项目根目录路径由 tests/__init__.py 统一设置

# 强制设置headless模式 - 确保不产生任何UI
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"  # 隐藏pygame启动提示

# 初始化pygame（headless模式）
pygame.init()

from src.core.ecs import EntityManager
from src.core.time_manager import TimeManager
from src.core.config_manager import ConfigManager
from src.world.grid import Grid, TERRAIN_GRASS, TERRAIN_DIRT, TERRAIN_WATER, ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL
from src.world.zone_manager import ZoneManager
from src.systems.job_system import JobSystem
from src.systems.action_system import ActionSystem
from src.systems.ai_system import AISystem
from src.systems.needs_system import NeedsSystem
from src.systems.farming_system import FarmingSystem
from src.systems.routine_system import RoutineSystem
from src.systems.survival_system import SurvivalSystem
from src.components.data_components import (
    PositionComponent, MovementComponent, ActionComponent, ResourceComponent,
    InventoryComponent, ItemComponent, HungerComponent, TirednessComponent,
    MoodComponent, RoutineComponent, ColdComponent
)
from src.components.skill_component import SkillComponent
from src.components.tags import IsVillager, IsTree


class TestWorld:
    """
    测试用的游戏世界
    
    完全headless模式，不创建任何UI组件（RenderSystem, UISystem等）。
    只包含核心逻辑系统，适合自动化测试。
    """
    
    def __init__(self, config_path: str = None, map_width: int = 40, map_height: int = 30):
        # 使用测试配置或默认配置
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "test_config.json")
            if not os.path.exists(config_path):
                config_path = "config/balance.json"
        
        self.config_manager = ConfigManager(config_path)
        global_conf = self.config_manager.get("global", {})
        
        tick_rate = global_conf.get("tick_rate", 60)
        sim_conf = self.config_manager.get("simulation", {})
        day_length = sim_conf.get("day_length_seconds", 10.0)
        season_length = sim_conf.get("season_length_days", 90)
        starting_season = sim_conf.get("starting_season", "spring")
        
        # 创建核心系统
        self.time_manager = TimeManager(
            tick_rate=tick_rate,
            day_length_seconds=day_length,
            season_length_days=season_length,
            starting_season=starting_season
        )
        
        # 设置Logger的时间管理器，并禁用日志输出（测试时减少输出）
        from src.utils.logger import Logger, LogCategory
        Logger.set_time_manager(self.time_manager)
        # 只启用ERROR类别，禁用其他类别以减少测试输出
        Logger.set_enabled_categories({LogCategory.ERROR})
        
        self.entity_manager = EntityManager()
        self.grid = Grid(map_width, map_height)
        self.zone_manager = ZoneManager(self.grid)
        self.job_system = JobSystem()
        
        # 创建系统
        self.action_system = ActionSystem(self.entity_manager, self.grid, self.config_manager, self.time_manager)
        self.ai_system = AISystem(
            self.entity_manager, self.job_system, self.grid,
            self.zone_manager, self.config_manager, self.time_manager
        )
        # 确保AI系统的_last_job_gen_tick初始值不会阻止第一次任务生成
        # 将初始值设置为-10，这样第一次检查时current_tick - (-10) >= 10会成立
        self.ai_system._last_job_gen_tick = -10
        
        self.needs_system = NeedsSystem(self.entity_manager, self.time_manager, self.config_manager)
        self.farming_system = FarmingSystem(
            self.entity_manager, self.job_system, self.grid,
            self.zone_manager, self.time_manager, self.config_manager
        )
        self.routine_system = RoutineSystem(self.entity_manager, self.time_manager, self.config_manager)
        self.survival_system = SurvivalSystem(
            self.entity_manager, self.time_manager, self.config_manager, self.grid
        )
        
        # 初始化地图
        self._init_map()
    
    def _init_map(self):
        """初始化测试地图"""
        # 创建简单的测试地图: 大部分是草地,有一些水域
        for x in range(self.grid.width):
            for y in range(self.grid.height):
                if x == self.grid.width - 5:  # 右侧有一列水域
                    self.grid.set_terrain(x, y, TERRAIN_WATER)
                else:
                    self.grid.set_terrain(x, y, TERRAIN_GRASS)
        
        # 创建基本区域
        center_x = self.grid.width // 2
        center_y = self.grid.height // 2
        
        # Stockpile区域
        for x in range(center_x - 2, center_x + 2):
            for y in range(center_y - 2, center_y + 2):
                if 0 <= x < self.grid.width and 0 <= y < self.grid.height:
                    self.zone_manager.mark_zone(x, y, ZONE_STOCKPILE)
        
        # Farm区域
        for x in range(center_x - 3, center_x + 3):
            for y in range(center_y + 5, center_y + 8):
                if 0 <= x < self.grid.width and 0 <= y < self.grid.height:
                    self.zone_manager.mark_zone(x, y, ZONE_FARM)
        
        # Residential区域
        for x in range(center_x - 2, center_x + 2):
            for y in range(center_y - 6, center_y - 3):
                if 0 <= x < self.grid.width and 0 <= y < self.grid.height:
                    self.zone_manager.mark_zone(x, y, ZONE_RESIDENTIAL)
    
    def update(self, dt: float = None):
        """更新游戏世界"""
        if dt is None:
            dt = self.time_manager.get_delta_time()
            if dt == 0:
                dt = 1.0 / self.time_manager.tick_rate
        
        # 手动推进时间管理器（不依赖真实时间）
        # 计算游戏时间推进
        day_length = self.config_manager.get("simulation.day_length_seconds", 10.0)
        hours_passed = (dt / day_length) * 24.0
        self.time_manager.time_of_day += hours_passed
        
        # 处理跨天
        if self.time_manager.time_of_day >= 24.0:
            self.time_manager.time_of_day -= 24.0
            self.time_manager.day += 1
            # 更新季节（如果方法存在）
            if hasattr(self.time_manager, '_update_season'):
                self.time_manager._update_season()
        
        # 更新其他系统
        self.time_manager.total_ticks += 1
        self.time_manager.delta_time = dt  # 设置delta_time供其他系统使用
        
        self.needs_system.update(dt)
        self.routine_system.update(dt)
        self.farming_system.update(dt)
        self.survival_system.update(dt)
        self.ai_system.update(dt)
        self.action_system.update(dt)
    
    def wait_ticks(self, num_ticks: int, max_ticks: int = None):
        """
        等待指定数量的tick
        
        Args:
            num_ticks: 要等待的tick数
            max_ticks: 最大tick数限制（防止无限循环），默认是num_ticks的10倍
        """
        if max_ticks is None:
            max_ticks = num_ticks * 10  # 默认最大限制
        
        actual_ticks = min(num_ticks, max_ticks)
        dt = self.time_manager.get_delta_time()
        if dt == 0:
            dt = 1.0 / self.time_manager.tick_rate
        
        for _ in range(actual_ticks):
            self.update(dt)
    
    def wait_game_time(self, hours: float, max_hours: float = None, max_iterations: int = 100000):
        """
        等待指定的游戏时间(小时)
        
        Args:
            hours: 要等待的游戏小时数
            max_hours: 最大等待时间限制（防止无限循环），默认是hours的2倍
            max_iterations: 最大迭代次数，防止无限循环
        """
        if max_hours is None:
            max_hours = max(hours * 2, 24.0)  # 至少限制在1天内
        
        day_length = self.config_manager.get("simulation.day_length_seconds", 10.0)
        initial_time = self.time_manager.time_of_day
        initial_day = self.time_manager.day
        
        # 计算目标时间（处理跨天）
        target_time = (initial_time + hours) % 24.0
        target_day = initial_day + int((initial_time + hours) // 24.0)
        
        # 计算需要推进的游戏时间（秒）
        target_seconds = (hours / 24.0) * day_length
        
        # 使用固定的dt来确保时间推进
        dt = 1.0 / self.time_manager.tick_rate  # 固定dt，不依赖真实时间
        
        iterations = 0
        elapsed_seconds = 0.0
        
        while elapsed_seconds < target_seconds and iterations < max_iterations:
            # 检查是否超过最大时间限制
            time_passed = (elapsed_seconds / day_length) * 24.0
            if time_passed >= max_hours:
                break
            
            # 检查是否跨天过多（防止无限循环）
            # 根据目标小时数计算允许的最大天数
            max_days = max(int(max_hours / 24.0) + 1, 1)
            if self.time_manager.day > initial_day + max_days:
                break
            
            # 更新系统（使用固定dt）
            self.update(dt)
            elapsed_seconds += dt
            iterations += 1
        
        if iterations >= max_iterations:
            raise TimeoutError(f"wait_game_time exceeded max_iterations ({max_iterations}) after {elapsed_seconds:.2f}s (target: {target_seconds:.2f}s)")


def create_test_villager(
    world: TestWorld,
    x: int = None,
    y: int = None,
    skills: dict = None,
    hunger: float = 30.0,
    tiredness: float = 15.0,
    mood: float = 65.0,
    cold: float = 10.0
) -> int:
    """创建测试用的村民"""
    if x is None:
        x = world.grid.width // 2
    if y is None:
        y = world.grid.height // 2
    if skills is None:
        skills = {"logging": 0.1, "farming": 0.1, "trapping": 0.1, "fishing": 0.1}
    
    villager = world.entity_manager.create_entity()
    world.entity_manager.add_component(villager, PositionComponent(x, y))
    
    move_speed_px = world.config_manager.get("entities.villager.move_speed", 50.0)
    pixels_per_unit = world.config_manager.get("global.pixels_per_unit", 32)
    move_speed_tiles = move_speed_px / pixels_per_unit
    world.entity_manager.add_component(villager, MovementComponent(speed=move_speed_tiles))
    world.entity_manager.add_component(villager, ActionComponent())
    world.entity_manager.add_component(villager, SkillComponent(skills=skills))
    world.entity_manager.add_component(villager, InventoryComponent(capacity=10))
    world.entity_manager.add_component(villager, HungerComponent(hunger=hunger))
    world.entity_manager.add_component(villager, TirednessComponent(tiredness=tiredness))
    world.entity_manager.add_component(villager, MoodComponent(mood=mood))
    world.entity_manager.add_component(villager, ColdComponent(cold=cold))
    world.entity_manager.add_component(villager, RoutineComponent())
    world.entity_manager.add_component(villager, IsVillager())
    
    return villager


def create_test_tree(world: TestWorld, x: int, y: int, health: int = 20) -> int:
    """创建测试用的树"""
    tree = world.entity_manager.create_entity()
    world.entity_manager.add_component(tree, PositionComponent(x, y))
    world.entity_manager.add_component(tree, ResourceComponent(
        resource_type="tree_oak",
        health=health,
        max_health=health,
        drops={"log": [3, 5]}
    ))
    world.entity_manager.add_component(tree, IsTree())
    
    return tree


def create_test_item(world: TestWorld, x: int, y: int, item_type: str, amount: int = 1) -> int:
    """创建测试用的物品"""
    item = world.entity_manager.create_entity()
    world.entity_manager.add_component(item, PositionComponent(x, y))
    
    food_value = world.config_manager.get(f"entities.items.{item_type}.food_value", 0.0)
    world.entity_manager.add_component(item, ItemComponent(
        item_type=item_type,
        amount=amount,
        food_value=food_value
    ))
    
    return item


def assert_villager_state(
    world: TestWorld,
    villager_id: int,
    position: tuple = None,
    hunger_range: tuple = None,
    tiredness_range: tuple = None,
    mood_range: tuple = None,
    action: str = None,
    has_item: str = None,
    item_count: int = None
):
    """验证村民状态（使用 AssertionError 以被测试框架正确捕获和追踪）"""
    pos = world.entity_manager.get_component(villager_id, PositionComponent)
    if position:
        if not (pos.x == position[0] and pos.y == position[1]):
            raise AssertionError(f"Expected position {position}, got ({pos.x}, {pos.y})")
    
    hunger = world.entity_manager.get_component(villager_id, HungerComponent)
    if hunger_range:
        if not (hunger_range[0] <= hunger.hunger <= hunger_range[1]):
            raise AssertionError(f"Expected hunger in range {hunger_range}, got {hunger.hunger}")
    
    tiredness = world.entity_manager.get_component(villager_id, TirednessComponent)
    if tiredness_range:
        if not (tiredness_range[0] <= tiredness.tiredness <= tiredness_range[1]):
            raise AssertionError(f"Expected tiredness in range {tiredness_range}, got {tiredness.tiredness}")
    
    mood = world.entity_manager.get_component(villager_id, MoodComponent)
    if mood_range:
        if not (mood_range[0] <= mood.mood <= mood_range[1]):
            raise AssertionError(f"Expected mood in range {mood_range}, got {mood.mood}")
    
    action_comp = world.entity_manager.get_component(villager_id, ActionComponent)
    if action:
        if action_comp.current_action != action:
            raise AssertionError(f"Expected action {action}, got {action_comp.current_action}")
    
    inv = world.entity_manager.get_component(villager_id, InventoryComponent)
    if has_item:
        if has_item not in inv.items:
            raise AssertionError(f"Expected item {has_item} in inventory")
        if item_count is not None:
            if inv.items[has_item] != item_count:
                raise AssertionError(f"Expected {item_count} {has_item}, got {inv.items[has_item]}")


def get_residential_tile(world: TestWorld):
    """返回地图上一个确定在住宅区的格子坐标（TestWorld._init_map 创建的区域）"""
    from src.world.grid import ZONE_RESIDENTIAL
    cx = world.grid.width // 2
    cy = world.grid.height // 2
    rx, ry = cx - 1, cy - 5
    assert world.grid.get_zone(rx, ry) == ZONE_RESIDENTIAL, \
        f"({rx},{ry}) should be residential but got zone {world.grid.get_zone(rx, ry)}"
    return rx, ry


def give_chop_job(world: TestWorld, villager_id: int, tree_id: int, tree_pos: tuple):
    """给村民分配一个砍树任务并设置为 move 状态"""
    from src.components.data_components import ActionComponent, MovementComponent, JobComponent
    from src.systems.job_system import Job

    job = Job(
        job_type="chop",
        target_pos=tree_pos,
        target_entity_id=tree_id,
        required_skill="logging",
        priority=1,
    )
    world.job_system.add_job(job)
    world.job_system.assign_job(job, villager_id)
    world.entity_manager.add_component(villager_id, JobComponent(
        job_id=job.id,
        job_type="chop",
        target_pos=tree_pos,
        target_entity_id=tree_id,
    ))
    action_comp = world.entity_manager.get_component(villager_id, ActionComponent)
    move_comp = world.entity_manager.get_component(villager_id, MovementComponent)
    action_comp.current_action = "move"
    move_comp.target = tree_pos
    move_comp.path = [tree_pos]
    return job


def assert_world_state(
    world: TestWorld,
    entity_count: int = None,
    job_count: int = None,
    tree_count: int = None
):
    """验证世界状态（使用 AssertionError 以被测试框架正确捕获和追踪）"""
    if entity_count is not None:
        actual_count = len(world.entity_manager._entities)
        if actual_count != entity_count:
            raise AssertionError(f"Expected {entity_count} entities, got {actual_count}")
    
    if job_count is not None:
        actual_jobs = len(world.job_system.get_available_jobs())
        if actual_jobs != job_count:
            raise AssertionError(f"Expected {job_count} available jobs, got {actual_jobs}")
    
    if tree_count is not None:
        trees = list(world.entity_manager.get_entities_with(IsTree))
        actual_trees = len(trees)
        if actual_trees != tree_count:
            raise AssertionError(f"Expected {tree_count} trees, got {actual_trees}")

