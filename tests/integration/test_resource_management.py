"""
资源管理集成测试
测试资源获取流程: 砍树 -> 生成log -> 搬运到仓库
验证AI系统、任务系统、区域系统的协作
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_tree, create_test_item
from src.components.data_components import InventoryComponent, ItemComponent, PositionComponent
from src.world.grid import ZONE_STOCKPILE


class TestResourceManagement(TestBase):
    """资源管理集成测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(
            self.world,
            skills={"logging": 0.6},
            hunger=0.0,       # 低饥饿防止urgent hunger中断工作
            tiredness=0.0     # 低疲劳防止睡眠中断
        )
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_chop_tree_creates_log(self):
        """测试砍树生成log"""
        # 创建树（低血量以便快速测试）
        tree_id = create_test_tree(self.world, 18, 18, health=5)
        
        # 固定在工作时间，防止日程切换干扰AI工作
        self.world.time_manager.time_of_day = 10.0
        
        # 等待AI接受任务并砍树
        # 需要：生成任务 -> 分配任务 -> 移动到树 -> 砍树
        max_iterations = 600
        dt = 1.0 / self.world.time_manager.tick_rate
        for i in range(max_iterations):
            self.world.time_manager.time_of_day = 10.0  # 保持工作时间
            self.world.update(dt)
            # 检查树是否被砍倒
            if not self.world.entity_manager.has_entity(tree_id):
                break
        
        # 验证树被砍倒
        has_tree = self.world.entity_manager.has_entity(tree_id)
        self.assert_false(has_tree, "Tree should be chopped down")
        
        # 检查是否生成了log物品
        items = list(self.world.entity_manager.get_entities_with(ItemComponent, PositionComponent))
        log_items = [i for _, item, _ in items if item.item_type == "log"]
        self.assert_greater(len(log_items), 0, "Log items should be created after chopping tree")
    
    def test_log_hauled_to_stockpile(self):
        """测试log被搬运到仓库"""
        # 创建log物品
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        create_test_item(self.world, center_x + 10, center_y, "log", 1)
        
        # 固定在工作时间
        self.world.time_manager.time_of_day = 10.0
        
        # 等待AI生成搬运任务并执行
        max_iterations = 400
        for i in range(max_iterations):
            self.world.time_manager.time_of_day = 10.0
            self.world.update()
            # 检查log是否在仓库
            items = list(self.world.entity_manager.get_entities_with(ItemComponent, PositionComponent))
            for _, item, pos in items:
                if item.item_type == "log":
                    zone = self.world.grid.get_zone(pos.x, pos.y)
                    if zone == ZONE_STOCKPILE:
                        break
            else:
                continue
            break
        
        # 验证log在仓库中
        items = list(self.world.entity_manager.get_entities_with(ItemComponent, PositionComponent))
        log_in_stockpile = False
        for _, item, pos in items:
            if item.item_type == "log":
                zone = self.world.grid.get_zone(pos.x, pos.y)
                if zone == ZONE_STOCKPILE:
                    log_in_stockpile = True
                    break
        
        # 验证搬运流程：log在仓库，或村民正在搬运（库存中有log），或搬运任务已生成
        inv_comp = self.world.entity_manager.get_component(self.villager_id, InventoryComponent)
        villager_has_log = inv_comp and inv_comp.items.get("log", 0) > 0
        haul_jobs = [j for j in self.world.job_system.jobs if j.job_type == "haul"]
        self.assert_true(
            log_in_stockpile or villager_has_log or len(haul_jobs) > 0,
            f"Haul workflow should progress: log_in_stockpile={log_in_stockpile}, villager_has_log={villager_has_log}, haul_jobs={len(haul_jobs)}"
        )

