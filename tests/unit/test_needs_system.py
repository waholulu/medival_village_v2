"""
需求系统单元测试
测试饥饿度增长、疲劳度变化、心情值变化、季节/日夜影响
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager
from src.components.data_components import ActionComponent, RoutineComponent, HungerComponent, TirednessComponent, MoodComponent


class TestNeedsSystem(TestBase):
    """需求系统测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(
            self.world,
            hunger=30.0,
            tiredness=15.0,
            mood=65.0
        )
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_hunger_increases_over_time(self):
        """测试饥饿度随时间增长"""
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        initial_hunger = hunger_comp.hunger
        
        # 等待一段时间(模拟1游戏小时)（限制最大等待时间）
        self.world.wait_game_time(1.0, max_hours=2.0)
        
        final_hunger = hunger_comp.hunger
        self.assert_greater(final_hunger, initial_hunger, "Hunger should increase over time")
    
    def test_tiredness_increases_when_working(self):
        """测试工作时疲劳度增加"""
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        
        initial_tiredness = tiredness_comp.tiredness
        action_comp.current_action = "chop"  # 设置为工作状态
        
        # 等待一段时间
        self.world.wait_game_time(1.0)
        
        final_tiredness = tiredness_comp.tiredness
        self.assert_greater(final_tiredness, initial_tiredness, "Tiredness should increase when working")
    
    def test_tiredness_decreases_when_sleeping(self):
        """测试睡眠时疲劳度减少"""
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        
        # 设置高疲劳度
        tiredness_comp.tiredness = 80.0
        action_comp.current_action = "sleep"
        
        initial_tiredness = tiredness_comp.tiredness
        
        # 等待一段时间（限制最大等待时间）
        self.world.wait_game_time(2.0, max_hours=4.0)
        
        final_tiredness = tiredness_comp.tiredness
        self.assert_less(final_tiredness, initial_tiredness, "Tiredness should decrease when sleeping")
    
    def test_mood_decreases_with_high_hunger(self):
        """测试高饥饿度时心情下降"""
        mood_comp = self.world.entity_manager.get_component(self.villager_id, MoodComponent)
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        
        # 设置高饥饿度
        hunger_comp.hunger = 85.0
        initial_mood = mood_comp.mood
        
        # 等待一段时间
        self.world.wait_game_time(1.0)
        
        final_mood = mood_comp.mood
        self.assert_less(final_mood, initial_mood, "Mood should decrease with high hunger")
    
    def test_mood_decreases_with_high_tiredness(self):
        """测试高疲劳度时心情下降"""
        mood_comp = self.world.entity_manager.get_component(self.villager_id, MoodComponent)
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        
        # 设置高疲劳度
        tiredness_comp.tiredness = 95.0
        initial_mood = mood_comp.mood
        
        # 等待一段时间
        self.world.wait_game_time(1.0)
        
        final_mood = mood_comp.mood
        self.assert_less(final_mood, initial_mood, "Mood should decrease with high tiredness")
    
    def test_mood_recovers_when_needs_met(self):
        """测试需求满足时心情恢复"""
        mood_comp = self.world.entity_manager.get_component(self.villager_id, MoodComponent)
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        
        # 设置低心情但需求满足
        mood_comp.mood = 30.0
        hunger_comp.hunger = 20.0  # 低饥饿
        tiredness_comp.tiredness = 10.0  # 低疲劳
        
        initial_mood = mood_comp.mood
        
        # 等待一段时间（限制最大等待时间）
        self.world.wait_game_time(2.0, max_hours=4.0)
        
        final_mood = mood_comp.mood
        self.assert_greater(final_mood, initial_mood, "Mood should recover when needs are met")
    
    def test_hunger_capped_at_100(self):
        """测试饥饿度上限为100"""
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        hunger_comp.hunger = 99.0
        
        # 等待很长时间（限制最大等待时间）
        self.world.wait_game_time(5.0, max_hours=10.0)  # 减少实际等待时间
        
        self.assert_less_equal(hunger_comp.hunger, 100.0, "Hunger should be capped at 100")
    
    def test_tiredness_capped_at_100(self):
        """测试疲劳度上限为100"""
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        
        tiredness_comp.tiredness = 99.0
        action_comp.current_action = "chop"  # 工作状态
        
        # 等待很长时间（限制最大等待时间）
        self.world.wait_game_time(5.0, max_hours=10.0)  # 减少实际等待时间
        
        self.assert_less_equal(tiredness_comp.tiredness, 100.0, "Tiredness should be capped at 100")
    
    def test_work_schedule_increases_hunger_faster(self):
        """工作状态应比休息更耗饥饿"""
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        routine_comp = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)

        self.world.time_manager.time_of_day = 8.0
        hunger_comp.hunger = 10.0
        routine_comp.current_state = "WORKING"
        action_comp.current_action = "chop"
        self.world.wait_game_time(1.0, max_hours=2.0)
        work_delta = hunger_comp.hunger - 10.0

        self.world.time_manager.time_of_day = 8.0
        hunger_comp.hunger = 10.0
        routine_comp.current_state = "RESTING"
        action_comp.current_action = "idle"
        self.world.wait_game_time(1.0, max_hours=2.0)
        rest_delta = hunger_comp.hunger - 10.0

        self.assert_greater(work_delta, rest_delta, "Working should consume more hunger than resting")

    def test_schedule_rest_reduces_tiredness(self):
        """作息中的休息段应恢复疲劳"""
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        routine_comp = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)

        day_length = self.world.config_manager.get("simulation.day_length_seconds", 120.0)
        one_hour_dt = day_length / 24.0

        # Rest window (summer midday)
        self.world.time_manager.current_season = "summer"
        self.world.time_manager.time_of_day = 14.0
        self.world.routine_system.update(0.0)
        tiredness_comp.tiredness = 60.0
        action_comp.current_action = "idle"
        self.world.needs_system.update(one_hour_dt)
        rest_value = tiredness_comp.tiredness

        # Working hour
        self.world.time_manager.time_of_day = 10.0
        tiredness_comp.tiredness = 60.0
        routine_comp.current_state = "WORKING"
        action_comp.current_action = "chop"
        self.world.needs_system.update(one_hour_dt)
        work_value = tiredness_comp.tiredness

        self.assert_less(rest_value, 60.0, "Rest segments should reduce tiredness")
        self.assert_greater(work_value, rest_value, "Working should accumulate more tiredness")

    def test_tiredness_capped_at_0(self):
        """测试疲劳度下限为0"""
        tiredness_comp = self.world.entity_manager.get_component(self.villager_id, TirednessComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        
        tiredness_comp.tiredness = 1.0
        action_comp.current_action = "sleep"
        
        # 等待很长时间（限制最大等待时间）
        self.world.wait_game_time(5.0, max_hours=10.0)  # 减少实际等待时间
        
        self.assert_greater_equal(tiredness_comp.tiredness, 0.0, "Tiredness should be capped at 0")

