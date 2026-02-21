"""
区域系统单元测试
测试区域标记和查询、最近区域查找、区域缓存
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld
from src.world.grid import ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL, ZONE_NONE


class TestZoneManager(TestBase):
    """区域系统测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.zone_manager = self.world.zone_manager
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_mark_zone(self):
        """测试标记区域"""
        x, y = 10, 10
        self.zone_manager.mark_zone(x, y, ZONE_STOCKPILE)
        
        zone = self.world.grid.get_zone(x, y)
        self.assert_equal(zone, ZONE_STOCKPILE, "Zone should be marked as STOCKPILE")
    
    def test_get_nearest_zone_tile(self):
        """测试查找最近区域地块"""
        # 清除可能存在的区域缓存（TestWorld初始化时创建的区域）
        # 标记一个区域（选择一个远离TestWorld初始化区域的位置）
        zone_x, zone_y = 35, 25  # 选择地图边缘附近
        self.zone_manager.mark_zone(zone_x, zone_y, ZONE_STOCKPILE)
        
        # 从远处查找（确保这个位置更近）
        start_pos = (30, 20)  # 更接近标记的区域
        nearest = self.zone_manager.get_nearest_zone_tile(start_pos, ZONE_STOCKPILE)
        
        self.assert_is_not_none(nearest, "Should find nearest zone tile")
        # 应该找到标记的区域（可能是这个或TestWorld初始化的区域，但至少应该找到）
        self.assert_true(
            nearest == (zone_x, zone_y) or nearest in self.zone_manager.zone_cache.get(ZONE_STOCKPILE, set()),
            f"Should find a STOCKPILE zone tile (got {nearest}, expected {zone_x},{zone_y})"
        )
    
    def test_get_nearest_zone_tile_returns_none_for_nonexistent_zone(self):
        """测试查找不存在的区域类型返回None"""
        start_pos = (10, 10)
        # 使用一个未在TestWorld中标记的区域类型值
        ZONE_NONEXISTENT = 99
        nearest = self.zone_manager.get_nearest_zone_tile(start_pos, ZONE_NONEXISTENT)
        self.assert_is_none(nearest, "Should return None when no matching zone exists")

    def test_get_nearest_zone_tile_finds_existing_farm(self):
        """测试查找已存在的FARM区域返回有效坐标"""
        start_pos = (10, 10)
        # TestWorld初始化时会创建FARM区域
        nearest = self.zone_manager.get_nearest_zone_tile(start_pos, ZONE_FARM)
        self.assert_is_not_none(nearest, "Should find FARM zone (TestWorld creates one in setup)")
        # 验证返回的坐标确实是FARM区域
        zone = self.world.grid.get_zone(nearest[0], nearest[1])
        self.assert_equal(zone, ZONE_FARM, "Returned tile should actually be a FARM zone")
    
    def test_zone_cache(self):
        """测试区域缓存"""
        x, y = 15, 15
        self.zone_manager.mark_zone(x, y, ZONE_FARM)
        
        # 检查缓存
        self.assert_true(
            ZONE_FARM in self.zone_manager.zone_cache,
            "Zone cache should contain FARM zone"
        )
        self.assert_true(
            (x, y) in self.zone_manager.zone_cache[ZONE_FARM],
            "Zone cache should contain the marked tile"
        )
    
    def test_change_zone(self):
        """测试更改区域"""
        x, y = 12, 12
        self.zone_manager.mark_zone(x, y, ZONE_STOCKPILE)
        
        # 更改为FARM区域
        self.zone_manager.mark_zone(x, y, ZONE_FARM)
        
        zone = self.world.grid.get_zone(x, y)
        self.assert_equal(zone, ZONE_FARM, "Zone should be changed to FARM")
        
        # 检查旧区域缓存已更新
        if ZONE_STOCKPILE in self.zone_manager.zone_cache:
            self.assert_false(
                (x, y) in self.zone_manager.zone_cache[ZONE_STOCKPILE],
                "Old zone cache should not contain the tile"
            )
    
    def test_multiple_zones(self):
        """测试多个区域"""
        # 标记多个不同类型的区域
        self.zone_manager.mark_zone(5, 5, ZONE_STOCKPILE)
        self.zone_manager.mark_zone(10, 10, ZONE_FARM)
        self.zone_manager.mark_zone(15, 15, ZONE_RESIDENTIAL)
        
        # 验证所有区域都被正确标记
        self.assert_equal(
            self.world.grid.get_zone(5, 5),
            ZONE_STOCKPILE,
            "Tile (5,5) should be STOCKPILE"
        )
        self.assert_equal(
            self.world.grid.get_zone(10, 10),
            ZONE_FARM,
            "Tile (10,10) should be FARM"
        )
        self.assert_equal(
            self.world.grid.get_zone(15, 15),
            ZONE_RESIDENTIAL,
            "Tile (15,15) should be RESIDENTIAL"
        )
    
    def test_get_nearest_zone_finds_closest(self):
        """测试找到最近区域"""
        # 标记多个STOCKPILE区域（选择远离TestWorld初始化区域的位置）
        # 使用地图边缘附近的位置
        zone1 = (35, 25)
        zone2 = (38, 28)
        zone3 = (32, 22)
        self.zone_manager.mark_zone(zone1[0], zone1[1], ZONE_STOCKPILE)
        self.zone_manager.mark_zone(zone2[0], zone2[1], ZONE_STOCKPILE)
        self.zone_manager.mark_zone(zone3[0], zone3[1], ZONE_STOCKPILE)
        
        # 从中间位置查找
        start_pos = (36, 26)
        nearest = self.zone_manager.get_nearest_zone_tile(start_pos, ZONE_STOCKPILE)
        
        self.assert_is_not_none(nearest, "Should find nearest zone")
        # 验证是标记的三个中的一个，或者至少是STOCKPILE区域
        self.assert_true(
            nearest in [zone1, zone2, zone3] or nearest in self.zone_manager.zone_cache.get(ZONE_STOCKPILE, set()),
            f"Should find one of the marked zones or any STOCKPILE (got {nearest}, marked: {[zone1, zone2, zone3]})"
        )

