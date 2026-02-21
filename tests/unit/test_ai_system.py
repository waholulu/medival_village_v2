"""
AI系统单元测试
测试任务查找和分配、紧急需求处理、工作执行流程
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_tree, create_test_item
from src.components.data_components import JobComponent, ActionComponent, HungerComponent, ItemComponent, PositionComponent
from src.systems.job_system import Job
from src.world.grid import ZONE_STOCKPILE


class TestAISystem(TestBase):
    """AI系统测试"""
    
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world, skills={"logging": 0.5})
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_ai_takes_available_job(self):
        """测试AI接受可用任务"""
        # 创建任务
        tree_id = create_test_tree(self.world, 15, 15)
        job = Job(
            job_type="chop",
            target_pos=(15, 15),
            target_entity_id=tree_id,
            required_skill="logging",
            priority=1
        )
        self.world.job_system.add_job(job)
        
        # 更新AI系统
        self.world.ai_system.update(0.1)
        
        # 检查村民是否接受了任务
        job_comp = self.world.entity_manager.get_component(self.villager_id, JobComponent)
        self.assert_is_not_none(job_comp, "Villager should have a job")
        self.assert_equal(job_comp.job_type, "chop", "Job type should be chop")
    
    def test_ai_handles_urgent_hunger(self):
        """测试AI处理紧急饥饿"""
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        
        # 设置高饥饿度
        hunger_comp.hunger = 85.0
        
        # 创建食物
        create_test_item(self.world, 20, 20, "food_wheat", 2)
        
        # 更新AI系统
        self.world.ai_system.update(0.1)
        
        # 检查是否开始寻找食物
        # AI应该设置移动或进食动作
        self.assert_true(
            action_comp.current_action in ["move", "eat"],
            "Villager should be moving to food or eating"
        )
    
    def test_ai_interrupts_job_for_urgent_hunger(self):
        """测试AI因紧急饥饿中断任务"""
        # 给村民一个任务
        tree_id = create_test_tree(self.world, 15, 15)
        job = Job(
            job_type="chop",
            target_pos=(15, 15),
            target_entity_id=tree_id,
            required_skill="logging",
            priority=1
        )
        self.world.job_system.add_job(job)
        self.world.job_system.assign_job(job, self.villager_id)
        
        job_comp = JobComponent(
            job_id=job.id,
            job_type="chop",
            target_pos=(15, 15),
            target_entity_id=tree_id
        )
        self.world.entity_manager.add_component(self.villager_id, job_comp)
        
        # 设置高饥饿度
        hunger_comp = self.world.entity_manager.get_component(self.villager_id, HungerComponent)
        hunger_comp.hunger = 85.0
        
        # 创建食物
        create_test_item(self.world, 20, 20, "food_wheat", 2)
        
        # 更新AI系统
        self.world.ai_system.update(0.1)
        
        # 检查任务是否被中断
        job_comp_after = self.world.entity_manager.get_component(self.villager_id, JobComponent)
        # 任务应该被移除或动作改变
        action_comp = self.world.entity_manager.get_component(self.villager_id, ActionComponent)
        self.assert_true(
            action_comp.current_action in ["move", "eat"] or job_comp_after is None,
            "Job should be interrupted for urgent hunger"
        )
    
    def test_ai_generates_haul_jobs(self):
        """测试AI生成搬运任务"""
        # 先清除所有现有的haul任务
        existing_haul_jobs = [j for j in self.world.job_system.jobs if j.job_type == "haul"]
        for job in existing_haul_jobs:
            self.world.job_system.jobs.remove(job)
        
        # 创建地面物品（确保不在仓库区域）
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        # 放在非仓库区域（远离TestWorld初始化的仓库区域）
        item_x = center_x + 15
        item_y = center_y + 15
        # 确保不在仓库区域
        zone = self.world.grid.get_zone(item_x, item_y)
        if zone == ZONE_STOCKPILE:
            # 如果碰巧在仓库，换个位置
            item_x = center_x - 15
            item_y = center_y - 15
        
        item_id = create_test_item(self.world, item_x, item_y, "log", 1)
        
        initial_jobs = len(self.world.job_system.get_available_jobs())
        
        # 更新整个系统(需要多次更新以触发任务生成，AI系统每10个tick生成一次任务)
        # 需要确保total_ticks正确更新，并且Logger._time_manager同步
        # 重置_last_job_gen_tick以确保任务生成
        self.world.ai_system._last_job_gen_tick = -10
        
        dt = 1.0 / self.world.time_manager.tick_rate
        for i in range(50):  # 确保超过10 tick的节流，并且有足够时间
            self.world.update(dt)
            # 检查是否已生成任务
            haul_jobs = [j for j in self.world.job_system.get_available_jobs() if j.job_type == "haul"]
            if len(haul_jobs) > 0:
                break
        
        # 应该生成搬运任务（当前可用的或已被分配的）
        haul_jobs = [j for j in self.world.job_system.get_available_jobs() if j.job_type == "haul"]
        any_haul_jobs = any(job.job_type == "haul" for job in self.world.job_system.jobs)
        self.assert_true(
            len(haul_jobs) > 0 or any_haul_jobs,
            f"Should generate haul jobs (available: {len(haul_jobs)}, total haul in system: {sum(1 for j in self.world.job_system.jobs if j.job_type == 'haul')}, total_ticks={self.world.time_manager.total_ticks})"
        )
    
    def test_ai_generates_chop_jobs(self):
        """测试AI生成砍树任务"""
        # 先清除所有现有的chop任务，确保不超过max_chop_jobs限制
        existing_chop_jobs = [j for j in self.world.job_system.jobs if j.job_type == "chop"]
        for job in existing_chop_jobs:
            self.world.job_system.jobs.remove(job)
        
        # 创建树（确保不在已有区域）
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        tree_x = center_x + 10
        tree_y = center_y + 10
        tree_id = create_test_tree(self.world, tree_x, tree_y)
        
        initial_jobs = len(self.world.job_system.get_available_jobs())
        
        # 更新整个系统(需要多次更新以触发任务生成，AI系统每10个tick生成一次任务)
        # 需要确保total_ticks正确更新，并且不超过max_chop_jobs限制（10个）
        # 重置_last_job_gen_tick以确保任务生成
        self.world.ai_system._last_job_gen_tick = -10
        
        dt = 1.0 / self.world.time_manager.tick_rate
        for i in range(50):  # 确保超过10 tick的节流，并且有足够时间
            self.world.update(dt)
            # 检查是否已生成任务
            chop_jobs = [j for j in self.world.job_system.get_available_jobs() if j.job_type == "chop"]
            if len(chop_jobs) > 0:
                break
        
        # 应该生成砍树任务（当前可用的或已被分配的）
        chop_jobs = [j for j in self.world.job_system.get_available_jobs() if j.job_type == "chop"]
        any_chop_jobs = any(job.job_type == "chop" for job in self.world.job_system.jobs)
        self.assert_true(
            len(chop_jobs) > 0 or any_chop_jobs,
            f"Should generate chop jobs (available: {len(chop_jobs)}, total chop in system: {sum(1 for j in self.world.job_system.jobs if j.job_type == 'chop')}, total_ticks={self.world.time_manager.total_ticks})"
        )

