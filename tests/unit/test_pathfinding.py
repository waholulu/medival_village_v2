"""
寻路系统单元测试
测试A*路径查找：直线路径、绕障碍、无路径、边界情况
"""
import tests

from tests.test_framework import TestBase
from src.world.grid import Grid, TERRAIN_GRASS, TERRAIN_WATER
from src.world.pathfinding import find_path, heuristic


class TestPathfindingBasic(TestBase):
    """寻路基础功能测试"""

    def setup(self):
        self.grid = Grid(20, 20)

    def test_straight_line_path(self):
        """直线路径"""
        path = find_path(self.grid, (0, 0), (5, 0))
        self.assert_greater(len(path), 0, "Should find a path")
        self.assert_equal(path[-1], (5, 0), "Path should end at target")

    def test_path_excludes_start(self):
        """路径不应包含起点"""
        path = find_path(self.grid, (0, 0), (3, 0))
        self.assert_not_contains(path, (0, 0), "Path should not include start position")

    def test_path_includes_end(self):
        """路径应包含终点"""
        path = find_path(self.grid, (0, 0), (3, 0))
        self.assert_contains(path, (3, 0), "Path should include end position")

    def test_adjacent_target(self):
        """相邻目标"""
        path = find_path(self.grid, (5, 5), (6, 5))
        self.assert_equal(len(path), 1, "Adjacent target should be 1 step")
        self.assert_equal(path[0], (6, 5))

    def test_same_start_and_end(self):
        """起点等于终点"""
        path = find_path(self.grid, (5, 5), (5, 5))
        self.assert_equal(len(path), 0, "Same start and end should return empty path")

    def test_diagonal_movement_not_allowed(self):
        """路径应为4方向移动（无对角线）"""
        path = find_path(self.grid, (0, 0), (3, 3))
        self.assert_greater(len(path), 0, "Should find a path")
        for i in range(1, len(path)):
            prev = path[i - 1] if i > 0 else (0, 0)
            curr = path[i]
            dx = abs(curr[0] - prev[0])
            dy = abs(curr[1] - prev[1])
            self.assert_equal(dx + dy, 1, f"Each step should move exactly 1 tile (step {i})")


class TestPathfindingObstacles(TestBase):
    """寻路障碍物测试"""

    def setup(self):
        self.grid = Grid(20, 20)

    def test_path_around_water(self):
        """路径应绕过水域"""
        for y in range(20):
            self.grid.set_terrain(5, y, TERRAIN_WATER)
        self.grid.set_terrain(5, 0, TERRAIN_GRASS)

        path = find_path(self.grid, (3, 10), (7, 10))
        self.assert_greater(len(path), 0, "Should find a path around water")
        for x, y in path:
            self.assert_true(
                self.grid.is_walkable(x, y),
                f"Path should only go through walkable tiles, but ({x},{y}) is not"
            )

    def test_no_path_when_blocked(self):
        """完全被水域包围时应无路径"""
        cx, cy = 10, 10
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if dx != 0 or dy != 0:
                    self.grid.set_terrain(cx + dx, cy + dy, TERRAIN_WATER)

        path = find_path(self.grid, (cx, cy), (0, 0))
        self.assert_equal(len(path), 0, "Should return empty path when surrounded by water")

    def test_path_to_impassable_target_returns_empty(self):
        """目标在水域时应返回空路径"""
        self.grid.set_terrain(10, 10, TERRAIN_WATER)
        path = find_path(self.grid, (0, 0), (10, 10))
        self.assert_equal(len(path), 0, "Should return empty path when target is water")

    def test_path_from_impassable_start_returns_empty(self):
        """起点在水域时应返回空路径"""
        self.grid.set_terrain(0, 0, TERRAIN_WATER)
        path = find_path(self.grid, (0, 0), (10, 10))
        self.assert_equal(len(path), 0, "Should return empty path when start is water")


class TestPathfindingBoundary(TestBase):
    """寻路边界条件测试"""

    def setup(self):
        self.grid = Grid(10, 10)

    def test_out_of_bounds_start(self):
        """起点超出边界应返回空"""
        path = find_path(self.grid, (-1, 0), (5, 5))
        self.assert_equal(len(path), 0, "OOB start should return empty path")

    def test_out_of_bounds_end(self):
        """终点超出边界应返回空"""
        path = find_path(self.grid, (0, 0), (10, 10))
        self.assert_equal(len(path), 0, "OOB end should return empty path")

    def test_corner_to_corner(self):
        """从一个角到另一个角"""
        path = find_path(self.grid, (0, 0), (9, 9))
        self.assert_greater(len(path), 0, "Should find path between corners")
        self.assert_equal(path[-1], (9, 9), "Should end at (9,9)")
        self.assert_equal(len(path), 18, "Manhattan distance is 18 steps")

    def test_path_along_border(self):
        """沿边界行走"""
        path = find_path(self.grid, (0, 0), (9, 0))
        self.assert_equal(len(path), 9, "Border path should be 9 steps")
        for x, y in path:
            self.assert_equal(y, 0, "Path should stay along y=0 border")


class TestHeuristic(TestBase):
    """启发函数测试"""

    def test_zero_distance(self):
        """同一点距离为0"""
        self.assert_almost_equal(heuristic((5, 5), (5, 5)), 0.0)

    def test_horizontal_distance(self):
        """水平距离"""
        self.assert_almost_equal(heuristic((0, 0), (3, 0)), 3.0)

    def test_vertical_distance(self):
        """垂直距离"""
        self.assert_almost_equal(heuristic((0, 0), (0, 4)), 4.0)

    def test_diagonal_distance(self):
        """对角距离（欧几里得）"""
        import math
        expected = math.sqrt(9 + 16)
        self.assert_almost_equal(heuristic((0, 0), (3, 4)), expected)
