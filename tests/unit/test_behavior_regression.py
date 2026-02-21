"""
Behavior regression tests for AI system fixes.
Covers: routine eating, inventory deposit, auto-pickup after chop,
stockpile deposit, and plant job seed check.
"""
import tests  # ensure sys.path setup

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_tree, create_test_item
from src.components.data_components import (
    JobComponent, ActionComponent, HungerComponent, InventoryComponent,
    PositionComponent, RoutineComponent, MovementComponent, TirednessComponent,
    ResourceComponent, ItemComponent, SleepStateComponent
)
from src.components.skill_component import SkillComponent
from src.components.tags import IsTree
from src.systems.job_system import Job
from src.world.grid import ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL


class TestRoutineEating(TestBase):
    """Test that villagers eat during scheduled EATING routine even with active jobs."""

    def setup(self):
        self.world = TestWorld()
        self.world.time_manager.time_of_day = 12.5  # Noon → EATING routine

    def teardown(self):
        self.world.config_manager.stop()

    def test_routine_eating_interrupts_active_job(self):
        """Villager with active job during EATING routine should release job and eat."""
        villager = create_test_villager(self.world, hunger=40.0)

        # Place food in stockpile area
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        create_test_item(self.world, center_x, center_y, "food_wheat", 5)

        # Give villager an active chop job
        tree_id = create_test_tree(self.world, 5, 5)
        job = Job(
            job_type="chop", target_pos=(5, 5),
            target_entity_id=tree_id, required_skill="logging", priority=4
        )
        self.world.job_system.add_job(job)
        self.world.job_system.assign_job(job, villager)
        self.world.entity_manager.add_component(villager, JobComponent(
            job_id=job.id, job_type="chop", target_pos=(5, 5), target_entity_id=tree_id
        ))

        # Set action to "move" (heading to tree)
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        action_comp.current_action = "move"

        # Update routine system to set EATING state
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        self.assert_equal(routine.current_state, "EATING", "Should be EATING at 12:30")

        # Update AI system - should interrupt job for meal
        self.world.ai_system.update(0.1)

        # Verify job was released
        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_none(job_comp, "Job should be released during EATING routine")

        # Verify eating or moving to food
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_true(
            action_comp.current_action in ["eat", "move"],
            f"Should be eating or moving to food, got {action_comp.current_action}"
        )

    def test_routine_eating_does_not_trigger_when_not_hungry(self):
        """Villager with low hunger during EATING routine should not interrupt job."""
        villager = create_test_villager(self.world, hunger=10.0)

        # Give villager a job
        tree_id = create_test_tree(self.world, 5, 5)
        job = Job(
            job_type="chop", target_pos=(5, 5),
            target_entity_id=tree_id, required_skill="logging", priority=4
        )
        self.world.job_system.add_job(job)
        self.world.job_system.assign_job(job, villager)
        self.world.entity_manager.add_component(villager, JobComponent(
            job_id=job.id, job_type="chop", target_pos=(5, 5), target_entity_id=tree_id
        ))
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        action_comp.current_action = "move"

        self.world.routine_system.update(0.1)
        self.world.ai_system.update(0.1)

        # Should still have job (hunger < 30, routine eating threshold)
        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_not_none(job_comp, "Job should NOT be interrupted when not hungry")


class TestInventoryDeposit(TestBase):
    """Test that villagers deposit inventory when entering non-work routines."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_deposit_all_items_before_sleep(self):
        """Villager should deposit ALL items (including food) when entering SLEEPING."""
        self.world.time_manager.time_of_day = 22.5  # Sleep time

        villager = create_test_villager(self.world, tiredness=50.0)

        # Put items in inventory
        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["food_wheat"] = 4
        inv.items["seed_wheat"] = 2
        inv.items["log"] = 1

        # Ensure idle + no job
        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        # Update routine and AI
        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        self.assert_equal(routine.current_state, "SLEEPING", "Should be SLEEPING at 22:30")

        self.world.ai_system.update(0.1)

        # Check inventory is empty
        self.assert_equal(len(inv.items), 0,
                          f"Inventory should be empty, got {inv.items}")

    def test_deposit_all_items_before_socializing(self):
        """Villager should deposit ALL items when entering SOCIALIZING."""
        self.world.time_manager.time_of_day = 20.0  # Leisure time

        villager = create_test_villager(self.world)

        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["food_wheat"] = 3
        inv.items["seed_wheat"] = 2

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        self.world.routine_system.update(0.1)
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        self.assert_equal(routine.current_state, "SOCIALIZING", "Should be SOCIALIZING at 20:00")

        self.world.ai_system.update(0.1)

        self.assert_equal(len(inv.items), 0,
                          f"Inventory should be empty after socializing deposit, got {inv.items}")

    def test_deposited_items_create_ground_entities(self):
        """Items deposited from inventory should become ground entities."""
        self.world.time_manager.time_of_day = 20.0

        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        villager = create_test_villager(self.world, x=center_x, y=center_y)

        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["log"] = 3

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        # Count ground items before
        items_before = sum(1 for _ in self.world.entity_manager.get_entities_with(ItemComponent, PositionComponent))

        self.world.routine_system.update(0.1)
        self.world.ai_system.update(0.1)

        # Count ground items after
        items_after = sum(1 for _ in self.world.entity_manager.get_entities_with(ItemComponent, PositionComponent))

        self.assert_greater(items_after, items_before,
                            "Ground items should increase after deposit")


class TestAutoPickupAfterChop(TestBase):
    """Test that villagers auto-pickup items after chopping a tree."""

    def setup(self):
        self.world = TestWorld()
        self.world.time_manager.time_of_day = 10.0  # Working time

    def teardown(self):
        self.world.config_manager.stop()

    def test_auto_pickup_items_at_chop_location(self):
        """After tree is destroyed, villager should auto-pickup dropped items."""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        # Create villager adjacent to where the tree was
        villager = create_test_villager(self.world, x=10, y=10, skills={"logging": 0.5})

        # Simulate: tree already destroyed, log dropped at tree position
        log_entity = create_test_item(self.world, 11, 10, "log", 1)

        # Create a chop job that references a non-existent tree (simulating destruction)
        job = Job(
            job_type="chop", target_pos=(11, 10),
            target_entity_id=99999,  # Non-existent entity
            required_skill="logging", priority=4
        )
        self.world.job_system.add_job(job)
        self.world.job_system.assign_job(job, villager)
        self.world.entity_manager.add_component(villager, JobComponent(
            job_id=job.id, job_type="chop", target_pos=(11, 10), target_entity_id=99999
        ))

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        self.world.routine_system.update(0.1)
        self.world.ai_system.update(0.1)

        # Check inventory now has the log
        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        self.assert_true(
            inv.items.get("log", 0) >= 1,
            f"Should have auto-picked up log, inv: {inv.items}"
        )

    def test_auto_pickup_triggers_move_to_stockpile(self):
        """After auto-pickup, villager should head to stockpile."""
        villager = create_test_villager(self.world, x=10, y=10, skills={"logging": 0.5})

        # Drop a log at tree position
        create_test_item(self.world, 11, 10, "log", 1)

        job = Job(
            job_type="chop", target_pos=(11, 10),
            target_entity_id=99999, required_skill="logging", priority=4
        )
        self.world.job_system.add_job(job)
        self.world.job_system.assign_job(job, villager)
        self.world.entity_manager.add_component(villager, JobComponent(
            job_id=job.id, job_type="chop", target_pos=(11, 10), target_entity_id=99999
        ))

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        self.world.routine_system.update(0.1)
        self.world.ai_system.update(0.1)

        # Should be moving to stockpile
        action = self.world.entity_manager.get_component(villager, ActionComponent)
        move = self.world.entity_manager.get_component(villager, MovementComponent)
        self.assert_equal(action.current_action, "move",
                          f"Should be moving to stockpile, got {action.current_action}")
        if move.target:
            target_zone = self.world.grid.get_zone(move.target[0], move.target[1])
            self.assert_equal(target_zone, ZONE_STOCKPILE,
                              "Movement target should be a stockpile tile")


class TestStockpileDeposit(TestBase):
    """Test that idle villagers at stockpile deposit their items."""

    def setup(self):
        self.world = TestWorld()
        self.world.time_manager.time_of_day = 10.0  # Working time

    def teardown(self):
        self.world.config_manager.stop()

    def test_idle_deposit_logs_at_stockpile(self):
        """Idle villager standing on stockpile with logs should deposit them."""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        villager = create_test_villager(self.world, x=center_x, y=center_y)

        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["log"] = 2

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        zone = self.world.grid.get_zone(center_x, center_y)
        self.assert_equal(zone, ZONE_STOCKPILE, "Villager should be on stockpile")

        self.world.routine_system.update(0.1)
        self.world.ai_system.update(0.1)

        # Logs should be deposited (removed from inventory)
        self.assert_equal(inv.items.get("log", 0), 0,
                          f"Logs should be deposited, inv: {inv.items}")

    def test_seeds_not_deposited_at_stockpile(self):
        """Idle villager at stockpile should NOT auto-deposit seeds (needed for planting)."""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        villager = create_test_villager(
            self.world, x=center_x, y=center_y,
            skills={"logging": 0.1, "farming": 0.5}
        )

        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["seed_wheat"] = 3

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        self.world.routine_system.update(0.1)
        self.world.ai_system.update(0.1)

        # Seeds should still be in inventory
        self.assert_equal(inv.items.get("seed_wheat", 0), 3,
                          "Seeds should NOT be auto-deposited at stockpile")


class TestPlantJobSeedCheck(TestBase):
    """Test that plant jobs are only assigned when seeds are available."""

    def setup(self):
        self.world = TestWorld()
        self.world.time_manager.time_of_day = 10.0

    def teardown(self):
        self.world.config_manager.stop()

    def test_no_plant_job_without_seeds(self):
        """Villager should NOT take plant job when no seeds exist anywhere."""
        villager = create_test_villager(
            self.world, skills={"logging": 0.1, "farming": 0.5}
        )

        # Create a plant job but NO seeds
        job = Job(
            job_type="plant", target_pos=(15, 20),
            required_skill="farming", priority=3
        )
        self.world.job_system.add_job(job)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        self.world.routine_system.update(0.1)
        self.world.ai_system.update(0.1)

        # Should NOT have taken the plant job
        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        if job_comp:
            self.assert_not_equal(job_comp.job_type, "plant",
                                  "Should not take plant job when no seeds available")

    def test_plant_job_with_seeds_in_inventory(self):
        """Villager WITH seeds should take plant job."""
        villager = create_test_villager(
            self.world, skills={"logging": 0.1, "farming": 0.5}
        )

        # Give seeds
        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["seed_wheat"] = 3

        # Create plant job at nearby farm tile
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        farm_y = center_y + 6  # Farm area in TestWorld
        job = Job(
            job_type="plant", target_pos=(center_x, farm_y),
            required_skill="farming", priority=3
        )
        self.world.job_system.add_job(job)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        self.world.routine_system.update(0.1)
        self.world.ai_system.update(0.1)

        # Should have taken the plant job
        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_not_none(job_comp, "Should take plant job when seeds available")
        self.assert_equal(job_comp.job_type, "plant",
                          "Job type should be plant")

    def test_plant_job_with_seeds_on_ground(self):
        """Plant job should be taken when seeds exist on ground (not in inventory)."""
        villager = create_test_villager(
            self.world, skills={"logging": 0.1, "farming": 0.5}
        )

        # Place seeds on ground near the villager
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2
        create_test_item(self.world, center_x + 1, center_y, "seed_wheat", 3)

        farm_y = center_y + 6
        job = Job(
            job_type="plant", target_pos=(center_x, farm_y),
            required_skill="farming", priority=3
        )
        self.world.job_system.add_job(job)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "idle"

        self.world.routine_system.update(0.1)
        self.world.ai_system.update(0.1)

        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_not_none(job_comp, "Should take plant job when seeds exist on ground")
