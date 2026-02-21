"""
时间管理器单元测试
测试时间推进、季节切换、日夜判断、暂停/恢复、时间缩放
"""
import tests

from tests.test_framework import TestBase
from src.core.time_manager import TimeManager


class TestTimeManagerBasic(TestBase):
    """时间管理器基础功能测试"""

    def setup(self):
        self.tm = TimeManager(tick_rate=60, day_length_seconds=10.0,
                              season_length_days=90, starting_season="spring")

    def test_initial_state(self):
        """初始状态应正确"""
        self.assert_equal(self.tm.day, 0, "Day should start at 0")
        self.assert_equal(self.tm.time_of_day, 6.0, "Should start at 6:00 AM")
        self.assert_equal(self.tm.current_season, "spring", "Should start in spring")
        self.assert_equal(self.tm.total_ticks, 0, "Total ticks should be 0")
        self.assert_false(self.tm.is_paused, "Should not be paused initially")

    def test_get_season(self):
        """get_season应返回当前季节"""
        self.assert_equal(self.tm.get_season(), "spring")
        self.tm.current_season = "winter"
        self.assert_equal(self.tm.get_season(), "winter")


class TestTimeManagerDayNight(TestBase):
    """日夜判断测试"""

    def setup(self):
        self.tm = TimeManager(tick_rate=60, day_length_seconds=10.0)

    def test_is_daytime_at_noon(self):
        """中午应为白天"""
        self.tm.time_of_day = 12.0
        self.assert_true(self.tm.is_daytime(), "12:00 should be daytime")

    def test_is_nighttime_at_midnight(self):
        """午夜应为夜晚"""
        self.tm.time_of_day = 0.0
        self.assert_true(self.tm.is_nighttime(), "0:00 should be nighttime")

    def test_is_daytime_at_boundary(self):
        """白天边界检查"""
        self.tm.time_of_day = 6.0
        self.assert_true(self.tm.is_daytime(), "6:00 is start of day")

        self.tm.time_of_day = 19.99
        self.assert_true(self.tm.is_daytime(), "19:59 is still daytime")

    def test_is_nighttime_at_boundary(self):
        """夜晚边界检查"""
        self.tm.time_of_day = 20.0
        self.assert_true(self.tm.is_nighttime(), "20:00 starts nighttime")

        self.tm.time_of_day = 5.99
        self.assert_true(self.tm.is_nighttime(), "5:59 is still nighttime")

    def test_day_night_state_dawn(self):
        """黎明状态"""
        self.tm.time_of_day = 5.5
        self.assert_equal(self.tm.get_day_night_state(), "dawn", "5:30 should be dawn")

        self.tm.time_of_day = 6.5
        self.assert_equal(self.tm.get_day_night_state(), "dawn", "6:30 should be dawn")

    def test_day_night_state_dusk(self):
        """黄昏状态（19:00-21:00）"""
        self.tm.time_of_day = 19.5
        self.assert_equal(self.tm.get_day_night_state(), "dusk", "19:30 should be dusk")

        self.tm.time_of_day = 20.5
        self.assert_equal(self.tm.get_day_night_state(), "dusk", "20:30 should still be dusk (range 19-21)")

        self.tm.time_of_day = 21.0
        self.assert_equal(self.tm.get_day_night_state(), "night", "21:00 should be night")

    def test_day_night_state_day(self):
        """白天状态"""
        self.tm.time_of_day = 12.0
        self.assert_equal(self.tm.get_day_night_state(), "day", "12:00 should be day")

    def test_day_night_state_night(self):
        """夜晚状态"""
        self.tm.time_of_day = 23.0
        self.assert_equal(self.tm.get_day_night_state(), "night", "23:00 should be night")

        self.tm.time_of_day = 3.0
        self.assert_equal(self.tm.get_day_night_state(), "night", "3:00 should be night")


class TestTimeManagerSeason(TestBase):
    """季节切换测试"""

    def setup(self):
        self.tm = TimeManager(tick_rate=60, day_length_seconds=10.0,
                              season_length_days=90, starting_season="spring")

    def test_season_changes_at_boundary(self):
        """季节应在day=season_length_days时切换"""
        self.tm.day = 89
        self.tm._update_season()
        self.assert_equal(self.tm.current_season, "spring", "Day 89 should still be spring")

        self.tm.day = 90
        self.tm._update_season()
        self.assert_equal(self.tm.current_season, "summer", "Day 90 should be summer")

    def test_full_year_cycle(self):
        """一整年的季节循环"""
        self.tm.day = 0
        self.tm._update_season()
        self.assert_equal(self.tm.current_season, "spring")

        self.tm.day = 90
        self.tm._update_season()
        self.assert_equal(self.tm.current_season, "summer")

        self.tm.day = 180
        self.tm._update_season()
        self.assert_equal(self.tm.current_season, "autumn")

        self.tm.day = 270
        self.tm._update_season()
        self.assert_equal(self.tm.current_season, "winter")

    def test_season_wraps_after_year(self):
        """超过一年后季节应循环"""
        self.tm.day = 360  # 360 / 90 = 4, 4 % 4 = 0 → spring
        self.tm._update_season()
        self.assert_equal(self.tm.current_season, "spring", "Day 360 should wrap to spring")

        self.tm.day = 450  # 450 / 90 = 5, 5 % 4 = 1 → summer
        self.tm._update_season()
        self.assert_equal(self.tm.current_season, "summer", "Day 450 should wrap to summer")


class TestTimeManagerPauseAndScale(TestBase):
    """暂停与时间缩放测试"""

    def setup(self):
        self.tm = TimeManager(tick_rate=60, day_length_seconds=10.0)

    def test_toggle_pause(self):
        """暂停切换"""
        self.assert_false(self.tm.is_paused)
        self.tm.toggle_pause()
        self.assert_true(self.tm.is_paused, "Should be paused after toggle")
        self.tm.toggle_pause()
        self.assert_false(self.tm.is_paused, "Should be unpaused after second toggle")

    def test_paused_delta_time_is_zero(self):
        """暂停时delta_time应为0"""
        self.tm.is_paused = True
        self.tm.use_fixed_dt = True
        self.tm.update()
        self.assert_equal(self.tm.delta_time, 0.0, "Delta time should be 0 when paused")

    def test_time_scale_clamped(self):
        """时间缩放应被限制在[0, 10]"""
        self.tm.set_time_scale(5.0)
        self.assert_equal(self.tm.time_scale, 5.0, "Scale should be 5.0")

        self.tm.set_time_scale(-1.0)
        self.assert_equal(self.tm.time_scale, 0.0, "Negative scale should be clamped to 0")

        self.tm.set_time_scale(20.0)
        self.assert_equal(self.tm.time_scale, 10.0, "Scale > 10 should be clamped to 10")

    def test_fixed_dt_mode(self):
        """固定dt模式应使用target_dt"""
        self.tm.use_fixed_dt = True
        self.tm.update()
        expected_dt = 1.0 / 60.0
        self.assert_almost_equal(self.tm.delta_time, expected_dt, tolerance=0.001,
                                 message="Fixed dt should equal target_dt")
