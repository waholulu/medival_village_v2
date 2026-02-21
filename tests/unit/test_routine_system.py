"""
作息系统单元测试
测试日程状态切换、季节性调整、各时间段对应的活动状态
"""
import tests

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager
from src.components.data_components import RoutineComponent, ActionComponent


class TestRoutineStateTransitions(TestBase):
    """作息系统状态切换测试"""

    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world)

    def teardown(self):
        self.world.config_manager.stop()

    def test_sleeping_at_midnight(self):
        """午夜应为SLEEPING"""
        self.world.time_manager.time_of_day = 0.0
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "SLEEPING", "Midnight should be SLEEPING")

    def test_sleeping_at_23(self):
        """23:00应为SLEEPING"""
        self.world.time_manager.time_of_day = 23.0
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "SLEEPING", "23:00 should be SLEEPING")

    def test_eating_at_breakfast(self):
        """早餐时段应为EATING"""
        self.world.time_manager.time_of_day = 7.0
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "EATING", "7:00 (breakfast) should be EATING")

    def test_eating_at_lunch(self):
        """午餐时段应为EATING"""
        self.world.time_manager.time_of_day = 12.5
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "EATING", "12:30 (lunch) should be EATING")

    def test_eating_at_dinner(self):
        """晚餐时段应为EATING"""
        self.world.time_manager.time_of_day = 18.5
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "EATING", "18:30 (dinner) should be EATING")

    def test_working_at_morning(self):
        """上午工作时段应为WORKING"""
        self.world.time_manager.time_of_day = 10.0
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "WORKING", "10:00 should be WORKING")

    def test_working_at_afternoon(self):
        """下午工作时段应为WORKING"""
        self.world.time_manager.time_of_day = 15.0
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "WORKING", "15:00 should be WORKING")

    def test_socializing_at_leisure(self):
        """休闲时段应为SOCIALIZING"""
        self.world.time_manager.time_of_day = 20.0
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "SOCIALIZING", "20:00 should be SOCIALIZING")


class TestRoutineSeasonalAdjustment(TestBase):
    """作息系统季节性调整测试"""

    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world)

    def teardown(self):
        self.world.config_manager.stop()

    def test_summer_midday_rest(self):
        """夏季午间应为RESTING"""
        self.world.time_manager.current_season = "summer"
        self.world.time_manager.time_of_day = 14.0
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "RESTING",
                          "Summer 14:00 should be RESTING (midday rest)")

    def test_spring_no_midday_rest(self):
        """春季午间不应有RESTING"""
        self.world.time_manager.current_season = "spring"
        self.world.time_manager.time_of_day = 14.0
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "WORKING",
                          "Spring 14:00 should be WORKING (no midday rest)")

    def test_winter_earlier_sleep(self):
        """冬季应更早进入SLEEPING"""
        self.world.time_manager.current_season = "winter"
        self.world.time_manager.time_of_day = 21.5
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_equal(routine.current_state, "SLEEPING",
                          "Winter 21:30 should be SLEEPING (earlier bedtime)")


class TestRoutineHelperMethods(TestBase):
    """作息系统辅助方法测试"""

    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world)

    def teardown(self):
        self.world.config_manager.stop()

    def test_should_eat(self):
        """should_eat在EATING状态应返回True"""
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        routine.current_state = "EATING"
        self.assert_true(self.world.routine_system.should_eat(self.villager_id))

    def test_should_not_eat_when_working(self):
        """should_eat在WORKING状态应返回False"""
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        routine.current_state = "WORKING"
        self.assert_false(self.world.routine_system.should_eat(self.villager_id))

    def test_should_sleep(self):
        """should_sleep在SLEEPING状态应返回True"""
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        routine.current_state = "SLEEPING"
        self.assert_true(self.world.routine_system.should_sleep(self.villager_id))

    def test_should_work(self):
        """should_work在WORKING状态应返回True"""
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        routine.current_state = "WORKING"
        self.assert_true(self.world.routine_system.should_work(self.villager_id))

    def test_should_eat_nonexistent_entity(self):
        """对不存在的实体查询应返回False"""
        self.assert_false(self.world.routine_system.should_eat(99999))

    def test_next_scheduled_activity_set(self):
        """更新后应设置next_scheduled_activity"""
        self.world.time_manager.time_of_day = 10.0
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(self.villager_id, RoutineComponent)
        self.assert_is_not_none(routine.next_scheduled_activity,
                                "next_scheduled_activity should be set after update")
