"""
农业系统单元测试
测试作物生长进度、种植任务生成、收获任务生成、季节影响
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_item
from src.components.data_components import CropComponent, PositionComponent
from src.world.grid import ZONE_FARM


class TestFarmingSystem(TestBase):
    """农业系统测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world, skills={"farming": 0.5})
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_crop_grows_over_time(self):
        """测试作物随时间生长"""
        # 创建作物
        crop_entity = self.world.entity_manager.create_entity()
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        
        self.world.entity_manager.add_component(crop_entity, PositionComponent(center_x, center_y))
        self.world.entity_manager.add_component(crop_entity, CropComponent(
            crop_type="wheat",
            growth_progress=0.0,
            state="growing"
        ))
        
        crop_comp = self.world.entity_manager.get_component(crop_entity, CropComponent)
        initial_progress = crop_comp.growth_progress
        
        # 等待一段时间（限制最大等待时间）
        self.world.wait_game_time(6.0, max_hours=12.0)  # 等待半天，但限制最大时间
        
        final_progress = crop_comp.growth_progress
        self.assert_greater(final_progress, initial_progress, "Crop should grow over time")
    
    def test_crop_becomes_ripe(self):
        """测试作物成熟"""
        # 创建接近成熟的作物
        crop_entity = self.world.entity_manager.create_entity()
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        
        self.world.entity_manager.add_component(crop_entity, PositionComponent(center_x, center_y))
        self.world.entity_manager.add_component(crop_entity, CropComponent(
            crop_type="wheat",
            growth_progress=0.95,
            state="growing"
        ))
        
        crop_comp = self.world.entity_manager.get_component(crop_entity, CropComponent)
        
        # 等待一段时间让作物成熟（限制最大等待时间）
        # 从0.95到1.0需要0.05的增长，根据growth_days=6.0计算
        # 每天增长1/6，所以0.05需要约0.3天 ≈ 7.2小时
        self.world.wait_game_time(8.0, max_hours=12.0)  # 等待8小时以确保成熟
        
        # 重新获取组件（可能已被更新）
        crop_comp_after = self.world.entity_manager.get_component(crop_entity, CropComponent)
        if crop_comp_after:
            self.assert_equal(crop_comp_after.state, "ripe", f"Crop should become ripe (current state: {crop_comp_after.state}, progress: {crop_comp_after.growth_progress:.2f})")
            self.assert_greater_equal(crop_comp_after.growth_progress, 1.0, f"Crop progress should be >= 1.0 when ripe (got {crop_comp_after.growth_progress:.2f})")
    
    def test_harvest_job_generated_for_ripe_crop(self):
        """测试为成熟作物生成收获任务"""
        # 创建成熟作物
        crop_entity = self.world.entity_manager.create_entity()
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2 + 5  # 在农场区域
        
        self.world.entity_manager.add_component(crop_entity, PositionComponent(center_x, center_y))
        self.world.entity_manager.add_component(crop_entity, CropComponent(
            crop_type="wheat",
            growth_progress=1.0,
            state="ripe"
        ))
        
        initial_jobs = len(self.world.job_system.get_available_jobs())
        
        # 更新系统
        self.world.farming_system.update(0.1)
        
        final_jobs = len(self.world.job_system.get_available_jobs())
        self.assert_greater(final_jobs, initial_jobs, "Harvest job should be generated for ripe crop")
        
        # 检查任务类型
        available_jobs = self.world.job_system.get_available_jobs()
        harvest_jobs = [j for j in available_jobs if j.job_type == "harvest"]
        self.assert_greater(len(harvest_jobs), 0, "Should have harvest jobs")
    
    def test_plant_job_generated_for_empty_farm_tile(self):
        """测试为空农场地块生成种植任务"""
        # 确保有种子
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2 + 5
        create_test_item(self.world, center_x, center_y, "seed_wheat", 5)
        
        initial_jobs = len(self.world.job_system.get_available_jobs())
        
        # 更新系统(需要多次更新以触发任务生成)
        for _ in range(25):  # 确保超过20 tick的节流
            self.world.farming_system.update(0.1)
            self.world.time_manager.total_ticks += 1
        
        final_jobs = len(self.world.job_system.get_available_jobs())
        # 应该有种植任务生成（农场区域有空地块且有种子可用）
        all_plant_jobs = [j for j in self.world.job_system.jobs if j.job_type == "plant"]
        self.assert_greater(
            len(all_plant_jobs), 0,
            f"Farming system should generate plant jobs when seeds exist and farm tiles are empty "
            f"(found {len(all_plant_jobs)} plant jobs, total_ticks={self.world.time_manager.total_ticks})"
        )
    
    def test_crop_growth_affected_by_season(self):
        """测试季节影响作物生长（春季生长，冬季不生长）"""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        
        # --- 春季：作物应该正常生长 ---
        crop_entity = self.world.entity_manager.create_entity()
        self.world.entity_manager.add_component(crop_entity, PositionComponent(center_x, center_y))
        self.world.entity_manager.add_component(crop_entity, CropComponent(
            crop_type="wheat",
            growth_progress=0.0,
            state="growing"
        ))
        
        crop_comp = self.world.entity_manager.get_component(crop_entity, CropComponent)
        self.world.time_manager.current_season = "spring"
        
        initial_progress = crop_comp.growth_progress
        self.world.wait_game_time(1.0, max_hours=2.0)
        spring_growth = crop_comp.growth_progress - initial_progress
        
        self.assert_greater(spring_growth, 0.0, "Crop should grow in spring")
        
        # --- 冬季：作物不应生长（growth_multiplier=0） ---
        crop_comp.growth_progress = 0.5
        crop_comp.state = "growing"
        self.world.time_manager.current_season = "winter"
        
        winter_initial = crop_comp.growth_progress
        self.world.wait_game_time(1.0, max_hours=2.0)
        winter_growth = crop_comp.growth_progress - winter_initial
        
        self.assert_less_equal(winter_growth, 0.0,
            f"Crop should not grow in winter (growth_multiplier=0), but grew by {winter_growth:.4f}")

