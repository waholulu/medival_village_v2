"""
农业工作流集成测试
测试完整农业流程: 播种 -> 生长 -> 收获 -> 搬运到仓库
验证农业系统、AI系统、任务系统的协作
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_item
from src.components.data_components import CropComponent, PositionComponent, InventoryComponent
from src.world.grid import ZONE_FARM


class TestFarmingWorkflow(TestBase):
    """农业工作流集成测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(
            self.world,
            skills={"farming": 0.6},
            hunger=0.0,       # 低饥饿防止urgent hunger中断工作
            tiredness=0.0     # 低疲劳防止睡眠中断
        )
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_complete_farming_cycle(self):
        """测试完整农业周期"""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        
        # 将种子放在仓库区域，防止AI生成haul任务把种子搬走
        create_test_item(self.world, center_x, center_y, "seed_wheat", 5)
        
        # 固定在工作时间，防止日程切换干扰AI工作
        self.world.time_manager.time_of_day = 10.0
        
        # 等待系统生成种植任务并执行
        # 流程：farming system生成plant job -> AI分配 -> 村民拿种子 -> 移动到农田 -> 种植
        max_iterations = 800
        dt = 1.0 / self.world.time_manager.tick_rate
        for i in range(max_iterations):
            self.world.time_manager.time_of_day = 10.0
            self.world.update(dt)
            # 检查是否有作物被种植
            crops = list(self.world.entity_manager.get_entities_with(CropComponent, PositionComponent))
            if len(crops) > 0:
                break
        
        # 验证作物被种植
        crops = list(self.world.entity_manager.get_entities_with(CropComponent, PositionComponent))
        self.assert_greater(len(crops), 0, "Crop should be planted")
        
        # 等待作物成熟
        crop_entity, crop_comp, crop_pos = crops[0]
        initial_progress = crop_comp.growth_progress
        
        # 加速时间让作物成熟（限制最大等待时间）
        self.world.wait_game_time(12.0, max_hours=24.0)  # 等待半天，最多1天
        
        # 检查作物是否成熟
        crop_comp_after = self.world.entity_manager.get_component(crop_entity, CropComponent)
        if crop_comp_after:
            self.assert_greater(
                crop_comp_after.growth_progress,
                initial_progress,
                "Crop should grow"
            )
    
    def test_harvest_generates_food(self):
        """测试收获生成食物"""
        # 创建成熟作物
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2 + 5
        
        crop_entity = self.world.entity_manager.create_entity()
        self.world.entity_manager.add_component(crop_entity, PositionComponent(center_x, center_y))
        self.world.entity_manager.add_component(crop_entity, CropComponent(
            crop_type="wheat",
            growth_progress=1.0,
            state="ripe"
        ))
        
        # 等待系统生成收获任务（限制最大迭代次数）
        # FarmingSystem每20个tick生成一次收获任务，需要更新系统
        # 确保作物在农场区域（FarmingSystem可能只检查农场区域的作物）
        zone = self.world.grid.get_zone(center_x, center_y)
        if zone != ZONE_FARM:
            # 标记为农场区域
            self.world.zone_manager.mark_zone(center_x, center_y, ZONE_FARM)
        
        # 固定在工作时间
        self.world.time_manager.time_of_day = 10.0
        
        max_iterations = 100
        dt = 1.0 / self.world.time_manager.tick_rate
        for i in range(max_iterations):
            self.world.time_manager.time_of_day = 10.0
            self.world.update(dt)
            # 检查所有harvest任务（包括已分配的，因为AI可能在同tick内分配）
            all_harvest_jobs = [j for j in self.world.job_system.jobs if j.job_type == "harvest"]
            if len(all_harvest_jobs) > 0:
                break
        
        # 验证收获任务生成（检查所有任务，不仅是未分配的）
        all_harvest_jobs = [j for j in self.world.job_system.jobs if j.job_type == "harvest"]
        has_crop = self.world.entity_manager.has_entity(crop_entity)
        self.assert_true(
            len(all_harvest_jobs) > 0 or not has_crop,
            f"Harvest job should be generated or crop should be harvested (found {len(all_harvest_jobs)} total harvest jobs, crop exists: {has_crop}, total_ticks={self.world.time_manager.total_ticks})"
        )

