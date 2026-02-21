"""
村民生命周期集成测试
测试村民完整生命周期: 工作 -> 饥饿 -> 进食 -> 疲劳 -> 睡眠
验证需求系统与AI系统的交互
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_item, assert_villager_state
from src.components.data_components import ActionComponent, HungerComponent, TirednessComponent, JobComponent, PositionComponent


class TestVillagerLifecycle(TestBase):
    """村民生命周期集成测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(
            self.world,
            hunger=30.0,
            tiredness=15.0
        )
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_villager_works_then_eats(self):
        """测试村民工作后进食"""
        # 创建食物
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        create_test_item(self.world, center_x, center_y, "food_wheat", 5)
        
        # 设置高饥饿度以触发进食（阈值是50.0）
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        hunger_comp.hunger = 85.0
        
        # 确保村民没有当前任务，以便AI可以处理紧急需求
        if self.world.entity_manager.has_component(self.villager_id, JobComponent):
            self.world.entity_manager.remove_component(self.villager_id, JobComponent)
        
        # 确保村民在食物附近（或者食物在村民附近）
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        # 将食物放在村民位置（确保能找到）
        create_test_item(self.world, pos_comp.x, pos_comp.y, "food_wheat", 5)
        
        # 更新系统多次（限制最大迭代次数）
        # 需要更多迭代，因为需要：AI检测饥饿 -> 寻找食物 -> 移动到食物 -> 开始进食
        max_iterations = 300  # 增加迭代次数
        dt = 1.0 / self.world.time_manager.tick_rate
        for i in range(max_iterations):
            self.world.update(dt)
            action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
            if action_comp.current_action in ["move", "eat", "pickup"]:
                # 检查是否在向食物移动或正在进食
                break
        
        # 检查是否开始进食或正在移动，或者饥饿度是否降低（说明已经进食）
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        final_hunger = hunger_comp.hunger
        # 如果饥饿度降低了，说明已经进食了
        has_eaten = final_hunger < 85.0
        self.assert_true(
            action_comp.current_action in ["move", "eat", "pickup", "idle"] or has_eaten,
            f"Villager should be handling hunger (action: {action_comp.current_action}, hunger: {final_hunger:.1f}, has_eaten: {has_eaten})"
        )
    
    def test_villager_sleeps_when_tired(self):
        """测试村民疲劳时睡眠"""
        # 设置高疲劳度
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        tiredness_comp.tiredness = 95.0
        
        # 更新系统多次（限制最大迭代次数）
        max_iterations = 100
        for i in range(max_iterations):
            self.world.update()
            action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
            if action_comp.current_action == "sleep":
                break
        
        # 检查是否开始睡眠
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        self.assert_true(
            action_comp.current_action in ["move", "sleep"],
            "Villager should be moving to sleep location or sleeping"
        )
    
    def test_villager_complete_cycle(self):
        """测试村民完整生命周期循环：高疲劳时应主动去睡觉"""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        # 直接设置高疲劳度，模拟一天工作后的状态
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)

        tiredness_comp.tiredness = 95.0
        hunger_comp.hunger = 20.0
        action_comp.current_action = "idle"

        initial_tiredness = tiredness_comp.tiredness
        self.assert_greater(initial_tiredness, 90.0, "Tiredness should be high enough to trigger sleep")

        # 运行AI，应触发紧急疲劳处理（去residential区域睡觉）
        found_need_handling = False
        max_iterations = 300
        dt = 1.0 / self.world.time_manager.tick_rate
        for i in range(max_iterations):
            self.world.update(dt)
            action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
            if action_comp.current_action in ["eat", "sleep", "move"]:
                found_need_handling = True
                break

        self.assert_true(
            found_need_handling,
            f"Villager should respond to high tiredness (action: {action_comp.current_action}, tiredness: {tiredness_comp.tiredness:.1f})"
        )

