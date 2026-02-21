"""
生存机制集成测试
测试生存系统与其他系统的协作:
  - 寒冷度随季节变化（冬季更冷）
  - 村民携带木头可以生火保暖（action_system + survival_system 联动）
  - 火源存在时多个村民同时受益
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_tree
from src.components.data_components import (
    ColdComponent, FireComponent, PositionComponent, InventoryComponent, ActionComponent
)


class TestSurvivalMechanics(TestBase):
    """生存机制集成测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world, cold=50.0)
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_winter_cold_increases_faster_than_spring(self):
        """测试冬季寒冷度比春季增长更快（集成：time_manager + survival_system）"""
        cold_comp = self.world.entity_manager.get_component(self.villager_id, ColdComponent)
        
        # 春季测试
        self.world.time_manager.current_season = "spring"
        self.world.time_manager.time_of_day = 12.0
        cold_comp.cold = 10.0
        self.world.wait_game_time(1.0, max_hours=2.0)
        spring_increase = cold_comp.cold - 10.0
        
        # 冬季测试
        self.world.time_manager.current_season = "winter"
        self.world.time_manager.time_of_day = 12.0
        cold_comp.cold = 10.0
        self.world.wait_game_time(1.0, max_hours=2.0)
        winter_increase = cold_comp.cold - 10.0
        
        self.assert_greater(winter_increase, spring_increase,
            f"Winter should increase cold faster than spring (winter: {winter_increase:.2f}, spring: {spring_increase:.2f})")
    
    def test_villager_builds_fire_with_logs(self):
        """测试村民使用木头生火（集成：inventory + action_system + survival_system）"""
        cold_comp = self.world.entity_manager.get_component(self.villager_id, ColdComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        inv_comp = self.world.entity_manager.get_component(self.villager_id, InventoryComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        
        # 给村民足够的木头来生火
        fire_cost = self.world.config_manager.get("entities.fire.fire_creation_cost_logs", 3)
        inv_comp.items["log"] = fire_cost
        
        # 设置高寒冷度并触发生火动作
        cold_comp.cold = 70.0
        action_comp.current_action = "create_fire"
        
        # 更新动作系统来执行生火
        self.world.action_system.update(0.1)
        
        # 检查结果：木头应该被消耗，火源应该被创建
        remaining_logs = inv_comp.items.get("log", 0)
        self.assert_less(remaining_logs, fire_cost,
            f"Logs should be consumed for fire (had {fire_cost}, now {remaining_logs})")
        
        # 检查是否有火源实体在村民附近
        fires = list(self.world.entity_manager.get_entities_with(FireComponent, PositionComponent))
        nearby_fires = [
            fire for _, fire, fpos in fires
            if abs(fpos.x - pos_comp.x) <= 1 and abs(fpos.y - pos_comp.y) <= 1
        ]
        self.assert_greater(len(nearby_fires), 0,
            f"Fire entity should exist near villager after build_fire action")
    
    def test_fire_warms_multiple_villagers(self):
        """测试火源同时温暖多个村民（集成：多实体 + survival_system）"""
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        cold_comp1 = self.world.entity_manager.get_component(self.villager_id, ColdComponent)
        
        # 创建第二个村民在同一位置
        villager2 = create_test_villager(self.world, x=pos_comp.x, y=pos_comp.y, cold=60.0)
        cold_comp2 = self.world.entity_manager.get_component(villager2, ColdComponent)
        
        # 设置两个村民的初始寒冷度
        cold_comp1.cold = 60.0
        initial_cold1 = cold_comp1.cold
        initial_cold2 = cold_comp2.cold
        
        # 在两个村民位置创建火源
        fire_entity = self.world.entity_manager.create_entity()
        self.world.entity_manager.add_component(fire_entity, PositionComponent(pos_comp.x, pos_comp.y))
        self.world.entity_manager.add_component(fire_entity, FireComponent(
            fuel_remaining=100.0,
            warmth_radius=5,
            fuel_consumption_per_hour=1.0
        ))
        
        # 等待一段时间
        self.world.wait_game_time(1.0, max_hours=2.0)
        
        # 两个村民的寒冷度都应该降低
        self.assert_less(cold_comp1.cold, initial_cold1,
            f"Villager 1 cold should decrease near fire (from {initial_cold1} to {cold_comp1.cold})")
        self.assert_less(cold_comp2.cold, initial_cold2,
            f"Villager 2 cold should decrease near fire (from {initial_cold2} to {cold_comp2.cold})")
