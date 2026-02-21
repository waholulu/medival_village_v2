"""
任务系统单元测试
测试Job创建、分配、优先级排序、完成和清理
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from src.systems.job_system import JobSystem, Job


class TestJobSystem(TestBase):
    """任务系统测试"""
    
    def setup(self):
        self.job_system = JobSystem()
    
    def test_add_job(self):
        """测试添加任务"""
        job = Job(
            job_type="chop",
            target_pos=(10, 20),
            priority=1
        )
        self.job_system.add_job(job)
        
        available = self.job_system.get_available_jobs()
        self.assert_equal(len(available), 1, "Should have 1 available job")
        self.assert_equal(available[0].job_type, "chop", "Job type should be chop")
    
    def test_job_priority_sorting(self):
        """测试任务优先级排序"""
        job1 = Job(job_type="chop", target_pos=(1, 1), priority=1)
        job2 = Job(job_type="haul", target_pos=(2, 2), priority=3)
        job3 = Job(job_type="plant", target_pos=(3, 3), priority=2)
        
        self.job_system.add_job(job1)
        self.job_system.add_job(job2)
        self.job_system.add_job(job3)
        
        available = self.job_system.get_available_jobs()
        # 高优先级在前
        self.assert_equal(available[0].priority, 3, "Highest priority job should be first")
        self.assert_equal(available[0].job_type, "haul", "Highest priority job should be haul")
        self.assert_equal(available[1].priority, 2, "Second priority should be 2")
        self.assert_equal(available[2].priority, 1, "Lowest priority should be 1")
    
    def test_assign_job(self):
        """测试分配任务"""
        job = Job(job_type="chop", target_pos=(10, 20), priority=1)
        self.job_system.add_job(job)
        
        entity_id = 123
        self.job_system.assign_job(job, entity_id)
        
        self.assert_equal(job.assignee, entity_id, "Job should be assigned to entity")
        
        available = self.job_system.get_available_jobs()
        self.assert_equal(len(available), 0, "Assigned job should not be available")
    
    def test_complete_job(self):
        """测试完成任务"""
        job = Job(job_type="chop", target_pos=(10, 20), priority=1)
        self.job_system.add_job(job)
        job_id = job.id
        
        self.job_system.complete_job(job_id)
        
        retrieved = self.job_system.get_job_by_id(job_id)
        self.assert_is_none(retrieved, "Completed job should be removed")
    
    def test_get_job_by_id(self):
        """测试通过ID获取任务"""
        job = Job(job_type="chop", target_pos=(10, 20), priority=1)
        self.job_system.add_job(job)
        job_id = job.id
        
        retrieved = self.job_system.get_job_by_id(job_id)
        self.assert_is_not_none(retrieved, "Job should be found by ID")
        self.assert_equal(retrieved.id, job_id, "Job ID should match")
        self.assert_equal(retrieved.job_type, "chop", "Job type should match")
    
    def test_get_available_jobs(self):
        """测试获取可用任务"""
        job1 = Job(job_type="chop", target_pos=(1, 1), priority=1)
        job2 = Job(job_type="haul", target_pos=(2, 2), priority=2)
        job3 = Job(job_type="plant", target_pos=(3, 3), priority=3)
        
        self.job_system.add_job(job1)
        self.job_system.add_job(job2)
        self.job_system.add_job(job3)
        
        # 分配一个任务
        self.job_system.assign_job(job2, 100)
        
        available = self.job_system.get_available_jobs()
        self.assert_equal(len(available), 2, "Should have 2 available jobs")
        self.assert_true(
            all(j.assignee is None for j in available),
            "All available jobs should have no assignee"
        )
    
    def test_multiple_jobs_same_type(self):
        """测试相同类型的多个任务"""
        for i in range(5):
            job = Job(job_type="chop", target_pos=(i, i), priority=1)
            self.job_system.add_job(job)
        
        available = self.job_system.get_available_jobs()
        self.assert_equal(len(available), 5, "Should have 5 available jobs")
        self.assert_true(
            all(j.job_type == "chop" for j in available),
            "All jobs should be chop type"
        )
    
    def test_job_with_required_skill(self):
        """测试带技能要求的任务"""
        job = Job(
            job_type="chop",
            target_pos=(10, 20),
            required_skill="logging",
            priority=1
        )
        self.job_system.add_job(job)
        
        retrieved = self.job_system.get_available_jobs()[0]
        self.assert_equal(retrieved.required_skill, "logging", "Job should require logging skill")
    
    def test_job_with_target_entity(self):
        """测试带目标实体的任务"""
        target_entity_id = 456
        job = Job(
            job_type="chop",
            target_pos=(10, 20),
            target_entity_id=target_entity_id,
            priority=1
        )
        self.job_system.add_job(job)
        
        retrieved = self.job_system.get_available_jobs()[0]
        self.assert_equal(
            retrieved.target_entity_id,
            target_entity_id,
            "Job should have target entity ID"
        )

    def test_complete_nonexistent_job(self):
        """完成不存在的任务不应崩溃"""
        self.job_system.complete_job("nonexistent-id")
        self.assert_equal(len(self.job_system.get_available_jobs()), 0,
                          "Should still have 0 jobs")

    def test_get_nonexistent_job_by_id(self):
        """查询不存在的任务ID应返回None"""
        result = self.job_system.get_job_by_id("nonexistent-id")
        self.assert_is_none(result, "Should return None for nonexistent job ID")

    def test_job_ids_are_unique(self):
        """每个任务应有唯一ID"""
        ids = set()
        for i in range(20):
            job = Job(job_type="chop", target_pos=(i, i), priority=1)
            self.job_system.add_job(job)
            self.assert_false(job.id in ids, f"Job ID {job.id} should be unique")
            ids.add(job.id)

