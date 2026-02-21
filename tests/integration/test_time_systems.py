"""
时间系统集成测试
测试时间系统影响: 季节变化对作物/需求的影响、日夜循环对工作效率的影响
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager
from src.components.data_components import CropComponent, PositionComponent, TirednessComponent, ActionComponent


class TestTimeSystems(TestBase):
    """时间系统集成测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world)
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_season_affects_crop_growth(self):
        """测试季节影响作物生长"""
        # 创建作物
        crop_entity = self.world.entity_manager.create_entity()
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        
        self.world.entity_manager.add_component(crop_entity, PositionComponent(center_x, center_y))
        self.world.entity_manager.add_component(crop_entity, CropComponent(
            crop_type="wheat",
            growth_progress=0.5,
            state="growing"
        ))
        
        crop_comp = self.world.entity_manager.get_component(crop_entity, CropComponent)
        initial_progress = crop_comp.growth_progress
        
        # 等待一段时间（限制最大等待时间）
        self.world.wait_game_time(2.0, max_hours=4.0)
        
        final_progress = crop_comp.growth_progress
        self.assert_greater(final_progress, initial_progress, "Crop should grow in spring")
    
    def test_day_night_cycle_affects_tiredness(self):
        """测试日夜循环影响疲劳度"""
        from src.components.data_components import RoutineComponent
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        routine_comp = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        
        # 设置为工作状态
        action_comp.current_action = "chop"
        tiredness_comp.tiredness = 50.0
        
        # 测试白天疲劳增长（限制最大等待时间）
        self.world.time_manager.time_of_day = 10.0  # 白天 (work_morning)
        if routine_comp:
            routine_comp.current_state = "WORKING"  # 确保日程也是工作状态
        initial_tiredness = tiredness_comp.tiredness
        
        # 手动推进并保持工作状态
        dt = 1.0 / self.world.time_manager.tick_rate
        for _ in range(120):  # ~2 seconds of sim time
            action_comp.current_action = "chop"  # 每帧强制工作状态
            if routine_comp:
                routine_comp.current_state = "WORKING"
            self.world.update(dt)
        day_increase = tiredness_comp.tiredness - initial_tiredness
        
        # 测试夜晚疲劳增长
        # 使用20:30作为夜晚时间（is_nighttime=True），但强制routine为WORKING
        action_comp.current_action = "chop"
        tiredness_comp.tiredness = 50.0
        self.world.time_manager.time_of_day = 20.5  # 夜晚
        if routine_comp:
            routine_comp.current_state = "WORKING"
        initial_tiredness = tiredness_comp.tiredness
        
        for _ in range(120):  # ~2 seconds of sim time
            action_comp.current_action = "chop"  # 每帧强制工作状态
            if routine_comp:
                routine_comp.current_state = "WORKING"
            self.world.update(dt)
        night_increase = tiredness_comp.tiredness - initial_tiredness
        
        # 夜晚应该增长更快（夜晚是白天的1.5倍）
        self.assert_greater(night_increase, day_increase, f"Tiredness should increase faster at night when working (day: {day_increase:.2f}, night: {night_increase:.2f})")

