"""
Tests for AI System regressions related to building and hauling.
Ensures that missing materials apply a job cooldown instead of an infinite loop.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager

from src.systems.ai_system import AISystem
from src.components.building_components import BlueprintComponent
from src.components.data_components import PositionComponent, JobComponent, ActionComponent
from src.systems.job_system import Job


class TestAIBuildingRegressions(TestBase):
    def setup(self):
        super().setup()

    def test_haul_to_blueprint_cooldown_when_no_materials(self):
        """Test that if a villager tries to haul to a blueprint but materials are missing, the job gets a cooldown."""
        world = TestWorld()
        
        # Create a villager
        villager = create_test_villager(world)
        
        # Add a haul_to_blueprint job
        job = Job(
            job_type="haul_to_blueprint",
            target_pos=(10, 10),
            target_entity_id=999, # Dummy blueprint ID
            metadata={"material_type": "log", "amount_needed": 5},
            priority=10
        )
        world.job_system.add_job(job)
        
        # Ensure the job is available
        available_jobs = world.job_system.get_available_jobs()
        self.assert_equal(len(available_jobs), 1, "Should have 1 available job")
        
        # Run AI system to assign the job
        world.ai_system.update(1.0)
        
        # Run Action System to process actions? Actually AI system processes the active job immediately via _process_job
        # Wait, the AI system assigns the job and *then* in the next tick _process_job is called, or in the same tick?
        # Let's run a second update for _process_job
        world.ai_system.update(1.0)
        
        # The villager should have released the job and put it on cooldown because there are no logs in the stockpile
        self.assert_false(world.entity_manager.has_component(villager, JobComponent), "Villager should have dropped the job")
        
        # Check action component is idle
        action_comp = world.entity_manager.get_component(villager, ActionComponent)
        self.assert_equal(action_comp.current_action, "idle", "Villager should be idle")
        
        # Check that the job is back in the job system but on cooldown in AI
        available_jobs_after = world.job_system.get_available_jobs()
        self.assert_equal(len(available_jobs_after), 1, "Job should be back in available pool")
        
        # Verify the cooldown exists
        self.assert_true(job.id in world.ai_system._failed_jobs_cooldown, "Job should be on cooldown")
        
        # Run AI system again, villager should NOT pick it up
        world.ai_system.update(1.0)
        self.assert_false(world.entity_manager.has_component(villager, JobComponent), "Villager should ignore job on cooldown")
