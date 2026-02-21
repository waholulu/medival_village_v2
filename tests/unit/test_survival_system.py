"""
生存系统单元测试
测试寒冷度增长(白天/夜晚)、火源燃料消耗、寒冷伤害机制、季节影响
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager
from src.components.data_components import ColdComponent, FireComponent, PositionComponent


class TestSurvivalSystem(TestBase):
    """生存系统测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world, cold=10.0)
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_cold_increases_over_time(self):
        """测试寒冷度随时间增长（夜晚场景，寒冷度应稳定增加）"""
        # Place villager far from residential zone to avoid shelter cold decay
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        pos_comp.x = 5
        pos_comp.y = 5

        cold_comp = self.world.entity_manager.get_component(self.villager_id, ColdComponent)
        
        # 设置为夜晚时间，确保寒冷度可靠增加
        # （白天在温暖季节如春天，温度补偿会导致寒冷度反而下降）
        self.world.time_manager.time_of_day = 22.0
        initial_cold = cold_comp.cold
        
        # 等待一段时间（限制最大等待时间）
        self.world.wait_game_time(2.0, max_hours=4.0)
        
        final_cold = cold_comp.cold
        self.assert_greater(final_cold, initial_cold, "Cold should increase over time at night")
    
    def test_cold_increases_faster_at_night(self):
        """测试夜晚寒冷度增长更快"""
        cold_comp = self.world.entity_manager.get_component(self.villager_id, ColdComponent)
        
        # 设置为白天时间
        self.world.time_manager.time_of_day = 12.0
        cold_comp.cold = 10.0
        self.world.wait_game_time(1.0)
        day_increase = cold_comp.cold - 10.0
        
        # 设置为夜晚时间
        self.world.time_manager.time_of_day = 22.0
        cold_comp.cold = 10.0
        self.world.wait_game_time(1.0)
        night_increase = cold_comp.cold - 10.0
        
        self.assert_greater(night_increase, day_increase, "Cold should increase faster at night")
    
    def test_fire_reduces_cold(self):
        """测试火源减少寒冷度"""
        cold_comp = self.world.entity_manager.get_component(self.villager_id, ColdComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        
        # 设置高寒冷度
        cold_comp.cold = 60.0  # 提高初始值以确保有足够空间减少
        
        # 在村民位置创建火源
        fire_entity = self.world.entity_manager.create_entity()
        self.world.entity_manager.add_component(fire_entity, PositionComponent(pos_comp.x, pos_comp.y))
        self.world.entity_manager.add_component(fire_entity, FireComponent(
            fuel_remaining=100.0,
            warmth_radius=5,
            fuel_consumption_per_hour=1.0
        ))
        
        initial_cold = cold_comp.cold
        
        # 等待一段时间（限制最大等待时间）
        self.world.wait_game_time(1.0, max_hours=2.0)
        
        final_cold = cold_comp.cold
        self.assert_less(final_cold, initial_cold, f"Cold should decrease near fire (from {initial_cold} to {final_cold})")
    
    def test_fire_consumes_fuel(self):
        """测试火源消耗燃料"""
        fire_entity = self.world.entity_manager.create_entity()
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        
        self.world.entity_manager.add_component(fire_entity, PositionComponent(center_x, center_y))
        fire_comp = FireComponent(
            fuel_remaining=100.0,
            warmth_radius=5,
            fuel_consumption_per_hour=1.0
        )
        self.world.entity_manager.add_component(fire_entity, fire_comp)
        
        initial_fuel = fire_comp.fuel_remaining
        
        # 等待一段时间（限制最大等待时间）
        self.world.wait_game_time(2.0, max_hours=4.0)
        
        final_fuel = fire_comp.fuel_remaining
        self.assert_less(final_fuel, initial_fuel, "Fire should consume fuel over time")
    
    def test_fire_extinguishes_when_fuel_runs_out(self):
        """测试燃料耗尽时火源熄灭"""
        fire_entity = self.world.entity_manager.create_entity()
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        
        self.world.entity_manager.add_component(fire_entity, PositionComponent(center_x, center_y))
        fire_comp = FireComponent(
            fuel_remaining=0.1,  # 很少的燃料
            warmth_radius=5,
            fuel_consumption_per_hour=10.0  # 高消耗率
        )
        self.world.entity_manager.add_component(fire_entity, fire_comp)
        
        # 等待一段时间让燃料耗尽
        self.world.wait_game_time(1.0)
        
        # 检查火源是否被销毁
        has_fire = self.world.entity_manager.has_entity(fire_entity)
        self.assert_false(has_fire, "Fire should be extinguished when fuel runs out")
    
    def test_cold_capped_at_100(self):
        """测试寒冷度上限为100"""
        cold_comp = self.world.entity_manager.get_component(self.villager_id, ColdComponent)
        cold_comp.cold = 99.0
        
        # 等待很长时间（限制最大等待时间）
        self.world.wait_game_time(5.0, max_hours=10.0)  # 减少实际等待时间
        
        self.assert_less_equal(cold_comp.cold, 100.0, "Cold should be capped at 100")
    
    def test_cold_capped_at_0(self):
        """测试寒冷度下限为0"""
        cold_comp = self.world.entity_manager.get_component(self.villager_id, ColdComponent)
        pos_comp = self.world.entity_manager.get_component(self.villager_id, PositionComponent)
        
        cold_comp.cold = 1.0
        
        # 创建火源
        fire_entity = self.world.entity_manager.create_entity()
        self.world.entity_manager.add_component(fire_entity, PositionComponent(pos_comp.x, pos_comp.y))
        self.world.entity_manager.add_component(fire_entity, FireComponent(
            fuel_remaining=100.0,
            warmth_radius=5,
            fuel_consumption_per_hour=1.0
        ))
        
        # 等待很长时间（限制最大等待时间）
        self.world.wait_game_time(5.0, max_hours=10.0)  # 减少实际等待时间
        
        self.assert_greater_equal(cold_comp.cold, 0.0, "Cold should be capped at 0")

