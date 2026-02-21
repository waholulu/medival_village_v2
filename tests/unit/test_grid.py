"""
Grid系统单元测试
测试地形设置/获取、可行走判断、区域设置/获取、边界检查
"""
import tests

from tests.test_framework import TestBase
from src.world.grid import (
    Grid, TERRAIN_GRASS, TERRAIN_DIRT, TERRAIN_WATER, TERRAIN_STONE,
    ZONE_NONE, ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL
)


class TestGrid(TestBase):
    """Grid基础功能测试"""

    def setup(self):
        self.grid = Grid(20, 15)

    def test_grid_dimensions(self):
        """网格尺寸应正确初始化"""
        self.assert_equal(self.grid.width, 20, "Width should be 20")
        self.assert_equal(self.grid.height, 15, "Height should be 15")

    def test_default_terrain_is_grass(self):
        """默认地形应为草地"""
        self.assert_equal(
            self.grid.get_terrain(0, 0), TERRAIN_GRASS,
            "Default terrain should be GRASS"
        )
        self.assert_equal(
            self.grid.get_terrain(10, 7), TERRAIN_GRASS,
            "Center tile should also default to GRASS"
        )

    def test_set_and_get_terrain(self):
        """设置和获取地形"""
        self.grid.set_terrain(5, 5, TERRAIN_DIRT)
        self.assert_equal(self.grid.get_terrain(5, 5), TERRAIN_DIRT, "Terrain should be DIRT")

        self.grid.set_terrain(3, 3, TERRAIN_STONE)
        self.assert_equal(self.grid.get_terrain(3, 3), TERRAIN_STONE, "Terrain should be STONE")

    def test_water_terrain_is_impassable(self):
        """水域地形应不可通行"""
        self.grid.set_terrain(5, 5, TERRAIN_WATER)
        self.assert_false(self.grid.is_walkable(5, 5), "Water should not be walkable")

    def test_grass_terrain_is_walkable(self):
        """草地地形应可通行"""
        self.assert_true(self.grid.is_walkable(0, 0), "Grass should be walkable")

    def test_dirt_terrain_is_walkable(self):
        """土地地形应可通行"""
        self.grid.set_terrain(5, 5, TERRAIN_DIRT)
        self.assert_true(self.grid.is_walkable(5, 5), "Dirt should be walkable")

    def test_stone_terrain_is_walkable(self):
        """石地地形应可通行"""
        self.grid.set_terrain(5, 5, TERRAIN_STONE)
        self.assert_true(self.grid.is_walkable(5, 5), "Stone should be walkable")


class TestGridBoundary(TestBase):
    """Grid边界条件测试"""

    def setup(self):
        self.grid = Grid(10, 10)

    def test_out_of_bounds_terrain_returns_negative(self):
        """超出边界的地形查询应返回-1"""
        self.assert_equal(self.grid.get_terrain(-1, 0), -1, "Negative x should return -1")
        self.assert_equal(self.grid.get_terrain(0, -1), -1, "Negative y should return -1")
        self.assert_equal(self.grid.get_terrain(10, 0), -1, "x=width should return -1")
        self.assert_equal(self.grid.get_terrain(0, 10), -1, "y=height should return -1")
        self.assert_equal(self.grid.get_terrain(100, 100), -1, "Far out of bounds should return -1")

    def test_out_of_bounds_not_walkable(self):
        """超出边界的位置应不可通行"""
        self.assert_false(self.grid.is_walkable(-1, 0), "Negative x should not be walkable")
        self.assert_false(self.grid.is_walkable(0, -1), "Negative y should not be walkable")
        self.assert_false(self.grid.is_walkable(10, 0), "x=width should not be walkable")
        self.assert_false(self.grid.is_walkable(0, 10), "y=height should not be walkable")

    def test_boundary_tiles_are_valid(self):
        """边界位置的地块应有效"""
        self.assert_equal(self.grid.get_terrain(0, 0), TERRAIN_GRASS, "Corner (0,0) should be valid")
        self.assert_equal(self.grid.get_terrain(9, 9), TERRAIN_GRASS, "Corner (9,9) should be valid")
        self.assert_equal(self.grid.get_terrain(9, 0), TERRAIN_GRASS, "Corner (9,0) should be valid")
        self.assert_equal(self.grid.get_terrain(0, 9), TERRAIN_GRASS, "Corner (0,9) should be valid")

    def test_set_terrain_out_of_bounds_is_safe(self):
        """超出边界的地形设置不应崩溃"""
        self.grid.set_terrain(-1, 0, TERRAIN_WATER)
        self.grid.set_terrain(0, -1, TERRAIN_WATER)
        self.grid.set_terrain(10, 0, TERRAIN_WATER)
        self.grid.set_terrain(0, 10, TERRAIN_WATER)
        self.assert_true(True, "Out of bounds set_terrain should not crash")

    def test_out_of_bounds_zone_returns_zero(self):
        """超出边界的区域查询应返回0 (ZONE_NONE)"""
        self.assert_equal(self.grid.get_zone(-1, 0), 0, "OOB zone should return 0")
        self.assert_equal(self.grid.get_zone(10, 0), 0, "OOB zone should return 0")


class TestGridZone(TestBase):
    """Grid区域功能测试"""

    def setup(self):
        self.grid = Grid(20, 15)

    def test_default_zone_is_none(self):
        """默认区域应为ZONE_NONE"""
        self.assert_equal(self.grid.get_zone(0, 0), ZONE_NONE, "Default zone should be NONE")

    def test_set_and_get_zone(self):
        """设置和获取区域"""
        self.grid.set_zone(5, 5, ZONE_STOCKPILE)
        self.assert_equal(self.grid.get_zone(5, 5), ZONE_STOCKPILE, "Zone should be STOCKPILE")

    def test_zone_does_not_affect_walkability(self):
        """设置区域不应影响可通行性"""
        self.grid.set_zone(5, 5, ZONE_STOCKPILE)
        self.assert_true(self.grid.is_walkable(5, 5), "Zone should not affect walkability")

    def test_zone_does_not_affect_terrain(self):
        """设置区域不应影响地形"""
        self.grid.set_zone(5, 5, ZONE_FARM)
        self.assert_equal(self.grid.get_terrain(5, 5), TERRAIN_GRASS, "Zone should not change terrain")

    def test_terrain_change_preserves_zone(self):
        """更改地形不应影响区域"""
        self.grid.set_zone(5, 5, ZONE_RESIDENTIAL)
        self.grid.set_terrain(5, 5, TERRAIN_DIRT)
        self.assert_equal(self.grid.get_zone(5, 5), ZONE_RESIDENTIAL, "Terrain change should not affect zone")

    def test_overwrite_zone(self):
        """覆写区域"""
        self.grid.set_zone(5, 5, ZONE_STOCKPILE)
        self.grid.set_zone(5, 5, ZONE_FARM)
        self.assert_equal(self.grid.get_zone(5, 5), ZONE_FARM, "Zone should be overwritten to FARM")
