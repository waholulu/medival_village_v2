"""
Tests for BuildingSystem functionality.
Ensures that blueprints correctly generate hauling and building jobs,
and transform into finished buildings when work is complete.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_item

from src.systems.building_system import BuildingSystem
from src.components.building_components import BlueprintComponent, BuildingComponent
from src.components.data_components import PositionComponent, InventoryComponent

class TestBuildingSystem(TestBase):
    def setup(self):
        super().setup()

    def test_blueprint_generates_hauling_jobs(self):
        """Test that a blueprint missing materials generates haul_to_blueprint jobs."""
        world = TestWorld()
        # Add building system to world manually since it's not in TestWorld by default
        building_sys = BuildingSystem(world.entity_manager, world.job_system, world.grid, world.config_manager)
        
        # Create a blueprint that needs 5 logs
        blueprint = world.entity_manager.create_entity()
        world.entity_manager.add_component(blueprint, PositionComponent(10, 10))
        world.entity_manager.add_component(blueprint, BlueprintComponent(
            building_type="test_building",
            required_materials={"log": 5},
            current_materials={},
            work_required=100.0,
            work_completed=0.0
        ))
        
        # Run building system
        building_sys.update(1.0)
        
        # Check that a haul_to_blueprint job was created
        jobs = world.job_system.jobs
        haul_jobs = [j for j in jobs if j.job_type == "haul_to_blueprint"]
        
        self.assert_equal(len(haul_jobs), 1, f"Expected 1 haul job, got {len(haul_jobs)}")
        self.assert_equal(haul_jobs[0].metadata["material_type"], "log", "")
        self.assert_equal(haul_jobs[0].metadata["amount_needed"], 5, "")
        self.assert_equal(haul_jobs[0].target_entity_id, blueprint, "")

    def test_blueprint_generates_build_job(self):
        """Test that a blueprint with all materials generates a build job."""
        world = TestWorld()
        building_sys = BuildingSystem(world.entity_manager, world.job_system, world.grid, world.config_manager)
        
        # Create a blueprint with all materials met
        blueprint = world.entity_manager.create_entity()
        world.entity_manager.add_component(blueprint, PositionComponent(10, 10))
        world.entity_manager.add_component(blueprint, BlueprintComponent(
            building_type="test_building",
            required_materials={"log": 5},
            current_materials={"log": 5},
            work_required=100.0,
            work_completed=0.0
        ))
        
        building_sys.update(1.0)
        
        jobs = world.job_system.jobs
        build_jobs = [j for j in jobs if j.job_type == "build"]
        
        self.assert_equal(len(build_jobs), 1, f"Expected 1 build job, got {len(build_jobs)}")
        self.assert_equal(build_jobs[0].target_entity_id, blueprint, "")

    def test_blueprint_transform(self):
        """Test that a completed blueprint transforms into a building."""
        world = TestWorld()
        building_sys = BuildingSystem(world.entity_manager, world.job_system, world.grid, world.config_manager)
        
        # Create a completed blueprint
        blueprint = world.entity_manager.create_entity()
        world.entity_manager.add_component(blueprint, PositionComponent(10, 10))
        world.entity_manager.add_component(blueprint, BlueprintComponent(
            building_type="test_building",
            required_materials={"log": 5},
            current_materials={"log": 5},
            work_required=100.0,
            work_completed=100.0 # Completed!
        ))
        
        building_sys.update(1.0)
        
        # Check that it transformed into a building
        self.assert_false(world.entity_manager.has_component(blueprint, BlueprintComponent), "Blueprint component should be removed")
        
        b_comp = world.entity_manager.get_component(blueprint, BuildingComponent)
        self.assert_is_not_none(b_comp, "Should have BuildingComponent")
        self.assert_equal(b_comp.building_type, "test_building", "")
