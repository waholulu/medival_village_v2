"""
动作系统单元测试
测试移动动作、砍树动作、拾取/放置动作、进食/睡眠动作
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_tree, create_test_item
from unittest.mock import patch
from src.components.data_components import (
    ActionComponent, MovementComponent, PositionComponent, InventoryComponent,
    HungerComponent, TirednessComponent, TrapComponent, ItemComponent
)


class TestActionSystem(TestBase):
    """动作系统测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world)
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_move_action(self):
        """测试移动动作"""
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        move_comp = self.world.entity_manager.get_component(self.villager_id, MovementComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        
        initial_pos = (pos_comp.x, pos_comp.y)
        target_pos = (pos_comp.x + 5, pos_comp.y)
        
        # 设置移动目标
        action_comp.current_action = "move"
        move_comp.target = target_pos
        
        # 更新动作系统多次以完成移动（限制最大迭代次数）
        max_iterations = 100
        for i in range(max_iterations):
            self.world.action_system.update(0.1)
            if action_comp.current_action == "idle":
                break
        
        # 检查位置是否改变
        final_pos = (pos_comp.x, pos_comp.y)
        self.assert_not_equal(final_pos, initial_pos, "Position should change after move")
    
    def test_chop_action(self):
        """测试砍树动作"""
        tree_id = create_test_tree(self.world, 15, 15, health=5)  # 低血量以便快速测试
        
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        
        # 移动到树附近
        pos_comp.x = 14
        pos_comp.y = 15
        
        # 设置砍树动作
        action_comp.current_action = "chop"
        action_comp.target_entity_id = tree_id
        
        # 更新动作系统直到树被砍倒（限制最大迭代次数）
        max_iterations = 150  # 减少迭代次数
        for i in range(max_iterations):
            self.world.action_system.update(0.1)
            if not self.world.entity_manager.has_entity(tree_id):
                break
        
        # 检查树是否被销毁
        has_tree = self.world.entity_manager.has_entity(tree_id)
        self.assert_false(has_tree, "Tree should be destroyed after chopping")
    
    def test_pickup_action(self):
        """测试拾取动作"""
        item_id = create_test_item(self.world, 12, 12, "log", 1)
        
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        inv_comp = self.world.entity_manager.get_component(self.villager_id, InventoryComponent)
        
        # 移动到物品位置
        pos_comp.x = 12
        pos_comp.y = 12
        
        # 设置拾取动作
        action_comp.current_action = "pickup"
        action_comp.target_entity_id = item_id
        
        # 更新动作系统
        self.world.action_system.update(0.1)
        
        # 检查物品是否在库存中
        self.assert_true("log" in inv_comp.items, "Item should be in inventory")
        self.assert_equal(inv_comp.items["log"], 1, "Should have 1 log")
        
        # 检查物品实体是否被销毁
        has_item = self.world.entity_manager.has_entity(item_id)
        self.assert_false(has_item, "Item entity should be destroyed after pickup")
    
    def test_drop_action(self):
        """测试放置动作"""
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        inv_comp = self.world.entity_manager.get_component(self.villager_id, InventoryComponent)
        
        # 给村民物品
        inv_comp.items["log"] = 2
        
        # 设置放置动作
        action_comp.current_action = "drop"
        
        # 更新动作系统
        self.world.action_system.update(0.1)
        
        # 检查物品是否从库存中移除（应该不在库存中或数量为0）
        item_count = inv_comp.items.get("log", 0)
        self.assert_true("log" not in inv_comp.items or item_count == 0,
                         f"Item should be removed from inventory, but got {item_count}")
        
        # 检查是否创建了物品实体
        from src.components.data_components import ItemComponent
        items = list(self.world.entity_manager.get_entities_with(ItemComponent, PositionComponent))
        log_items = [item for _, item, _ in items if item.item_type == "log"]
        self.assert_greater(len(log_items), 0, "Drop should create item entity on the ground")
    
    def test_eat_action(self):
        """测试进食动作"""
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        inv_comp = self.world.entity_manager.get_component(self.villager_id, InventoryComponent)
        
        # 设置高饥饿度和食物
        hunger_comp.hunger = 80.0
        inv_comp.items["food_wheat"] = 1
        
        # 设置进食动作
        action_comp.current_action = "eat"
        
        # 更新动作系统
        self.world.action_system.update(0.1)
        
        # 检查饥饿度是否降低
        self.assert_less(hunger_comp.hunger, 80.0, "Hunger should decrease after eating")
        
        # 检查食物是否被消耗（应该不在库存中或数量为0）
        food_count = inv_comp.items.get("food_wheat", 0)
        self.assert_true("food_wheat" not in inv_comp.items or food_count == 0,
                         f"Food should be consumed, but got {food_count}")
    
    def test_sleep_action(self):
        """测试睡眠动作"""
        from src.world.grid import ZONE_RESIDENTIAL
        
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        
        # 移动到住宅区域
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        pos_comp.x = center_x
        pos_comp.y = center_y - 5  # 在住宅区域
        
        # 设置高疲劳度
        tiredness_comp.tiredness = 90.0
        
        # 设置睡眠动作
        action_comp.current_action = "sleep"
        
        # 更新动作系统
        self.world.action_system.update(0.1)
        
        # 等待一段时间（限制最大等待时间）
        self.world.wait_game_time(1.0, max_hours=2.0)
        
        # 检查疲劳度是否降低
        self.assert_less(tiredness_comp.tiredness, 90.0, "Tiredness should decrease when sleeping")

    def test_trap_check_respects_interval(self):
        """陷阱检查应遵守冷却时间"""
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)

        trap_entity = self.world.entity_manager.create_entity()
        self.world.entity_manager.add_component(trap_entity, PositionComponent(pos_comp.x, pos_comp.y))
        trap_comp = TrapComponent(trap_type="basic_trap", durability=2.0, max_durability=2.0, last_check_time=0.0, catch_probability=0.15)
        self.world.entity_manager.add_component(trap_entity, trap_comp)

        trap_interval = self.world.config_manager.get("entities.trapping.trap_check_interval_hours", 6.0)
        current_hours = self.world.action_system._get_total_game_hours()

        # Too soon - should exit without updating timestamp
        trap_comp.last_check_time = current_hours - (trap_interval - 1.0)
        action_comp.current_action = "trap"
        action_comp.target_entity_id = trap_entity
        self.world.action_system.update(0.1)
        self.assert_equal(action_comp.current_action, "idle", "Trap action should cancel when interval not met")
        self.assert_equal(trap_comp.last_check_time, current_hours - (trap_interval - 1.0), "Trap timestamp should remain unchanged when cooling down")

        # After interval - timestamp should update
        trap_comp.last_check_time = current_hours - (trap_interval + 0.5)
        action_comp.current_action = "trap"
        with patch("src.systems.action_system.random.random", return_value=0.9):
            self.world.action_system.update(0.1)
        self.assert_equal(trap_comp.last_check_time, self.world.action_system._get_total_game_hours(), "Trap timestamp should refresh after a valid check")

    def test_fishing_respects_duration_and_time_window(self):
        """钓鱼需要完整耗时并受时间段限制"""
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)

        # Move to water column
        pos_comp.x = self.world.grid.width - 5
        pos_comp.y = self.world.grid.height // 2

        fishing_conf = self.world.config_manager.config.setdefault("entities", {}).setdefault("fishing", {})
        fishing_conf["fishing_time_per_attempt_seconds"] = 1.0
        fishing_conf["fishing_best_hours"] = [5.0, 7.0]

        self.world.time_manager.time_of_day = 6.0  # within best hour window
        action_comp.current_action = "fish"

        # Not enough time yet (initial frame just arms fishing)
        self.world.action_system.update(0.25)
        self.assert_equal(action_comp.current_action, "fish", "Fishing should continue before duration completes")

        with patch("src.systems.action_system.random.random", return_value=0.1):
            self.world.action_system.update(0.5)
            self.world.action_system.update(0.6)

        fish_items = [
            e for e, item, pos in self.world.entity_manager.get_entities_with(ItemComponent, PositionComponent)
            if item.item_type == "fish"
        ]
        self.assert_greater(len(fish_items), 0, "Fishing during best hour should yield fish")

        # Outside best hours cancels action immediately
        self.world.time_manager.time_of_day = 12.0
        action_comp.current_action = "fish"
        self.world.action_system.update(0.1)
        self.assert_equal(action_comp.current_action, "idle", "Fishing outside configured hours should stop")

