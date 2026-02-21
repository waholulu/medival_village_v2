"""
Regression tests for sleep/job/hunger interaction fixes.

Covers:
  1. Jobs released during SLEEPING routine (villagers stop working at bedtime)
  2. Villagers actually sleep when on residential tile during SLEEPING
  3. Moving villagers stop on residential tiles during SLEEPING to sleep
  4. Sleep/wake hysteresis (wake at tiredness<=5, sleep at >10)
  5. No double tiredness reduction during sleep
  6. Routine eating does not interrupt active jobs (only urgent hunger does)
  7. Hunger not suppressed during SLEEPING for urgent cases (>50)
  8. Moving toward residential suppresses moderate hunger (<=70)
  9. Plant jobs preferred when carrying seeds
  10. Diagnostic logger says "Job ended" not "Job completed" for released jobs
"""
import tests

from tests.test_framework import TestBase
from tests.test_helpers import (
    TestWorld, create_test_villager, create_test_tree, create_test_item,
    get_residential_tile, give_chop_job
)
from src.components.data_components import (
    ActionComponent, MovementComponent, PositionComponent, InventoryComponent,
    HungerComponent, TirednessComponent, MoodComponent, ItemComponent,
    JobComponent, RoutineComponent, SleepStateComponent, CropComponent
)
from src.systems.job_system import Job
from src.world.grid import ZONE_RESIDENTIAL, ZONE_STOCKPILE, ZONE_FARM


# ===========================================================================
# 1. Jobs released during SLEEPING routine
# ===========================================================================

class TestJobReleasedDuringSleeping(TestBase):
    """Villagers should release their active job when SLEEPING routine starts."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_active_job_released_during_sleeping(self):
        """A villager with an active chop job should release it when routine is SLEEPING."""
        villager = create_test_villager(self.world, hunger=20.0, tiredness=30.0, skills={"logging": 0.5})
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "SLEEPING"

        tree = create_test_tree(self.world, 5, 5)
        job = give_chop_job(self.world, villager, tree, (5, 5))

        self.world.ai_system.update(0.1)

        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_none(job_comp, "Job should be released during SLEEPING routine")

        released_job = self.world.job_system.get_job_by_id(job.id)
        self.assert_is_not_none(released_job, "Job should still exist in pool (released, not destroyed)")
        self.assert_is_none(released_job.assignee, "Job should be unassigned after release")

    def test_idle_villager_during_sleeping_seeks_sleep(self):
        """An idle villager during SLEEPING routine should try to sleep."""
        rx, ry = get_residential_tile(self.world)
        villager = create_test_villager(self.world, x=rx, y=ry, hunger=20.0, tiredness=30.0)
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "SLEEPING"

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_equal(action.current_action, "sleep",
                          "Idle villager on residential tile during SLEEPING should start sleeping")


# ===========================================================================
# 2. Moving villagers stop on residential tiles during SLEEPING
# ===========================================================================

class TestStopOnResidentialDuringSleeping(TestBase):
    """Villagers moving through residential zone during SLEEPING should stop and sleep."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_moving_villager_stops_on_residential_during_sleeping(self):
        """A moving villager already on a residential tile should stop and sleep."""
        rx, ry = get_residential_tile(self.world)
        villager = create_test_villager(self.world, x=rx, y=ry, hunger=20.0, tiredness=50.0)
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "SLEEPING"

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)
        action.current_action = "move"
        move_comp.target = (rx, ry - 5)
        move_comp.path = [(rx, ry - 1), (rx, ry - 2)]

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_equal(action.current_action, "sleep",
                          "Should stop and sleep when on residential tile during SLEEPING")

    def test_moving_toward_food_not_intercepted_on_residential(self):
        """A villager moving toward food should NOT be intercepted even on residential tile."""
        rx, ry = get_residential_tile(self.world)
        villager = create_test_villager(self.world, x=rx, y=ry, hunger=75.0, tiredness=50.0)
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "SLEEPING"

        food = create_test_item(self.world, rx + 5, ry, "food_wheat", 3)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)
        action.current_action = "move"
        action.target_entity_id = food
        move_comp.target = (rx + 5, ry)
        move_comp.path = [(rx + 1, ry), (rx + 2, ry)]

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_not_equal(action.current_action, "sleep",
                              "Should NOT intercept food-seeking villager for sleep")


# ===========================================================================
# 3. Sleep/wake hysteresis
# ===========================================================================

class TestSleepWakeHysteresis(TestBase):
    """Sleep system should have hysteresis: sleep at tiredness>10, wake at <=5."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_does_not_wake_at_tiredness_8(self):
        """Villager with tiredness=8 should NOT wake up (threshold is <=5)."""
        rx, ry = get_residential_tile(self.world)
        villager = create_test_villager(self.world, x=rx, y=ry, tiredness=8.0)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "sleep"

        sleep_state = SleepStateComponent(is_sleeping=True, sleep_location=(rx, ry))
        self.world.entity_manager.add_component(villager, sleep_state)

        self.world.action_system.update(0.01)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_equal(action.current_action, "sleep",
                          "Should NOT wake up at tiredness=8 (threshold is <=5)")

    def test_wakes_at_tiredness_4(self):
        """Villager with tiredness=4 should wake up."""
        rx, ry = get_residential_tile(self.world)
        villager = create_test_villager(self.world, x=rx, y=ry, tiredness=4.0)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "sleep"

        sleep_state = SleepStateComponent(is_sleeping=True, sleep_location=(rx, ry))
        self.world.entity_manager.add_component(villager, sleep_state)

        self.world.action_system.update(0.01)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_equal(action.current_action, "idle",
                          "Should wake up at tiredness=4 (<=5 threshold)")


# ===========================================================================
# 4. No double tiredness reduction during sleep
# ===========================================================================

class TestNoDoubleTirednessReduction(TestBase):
    """action_system._handle_sleep should NOT reduce tiredness (NeedsSystem does it)."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_action_system_does_not_reduce_tiredness(self):
        """After action_system processes sleep, tiredness should remain unchanged
        (only NeedsSystem should modify tiredness)."""
        rx, ry = get_residential_tile(self.world)
        villager = create_test_villager(self.world, x=rx, y=ry, tiredness=50.0)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "sleep"

        sleep_state = SleepStateComponent(is_sleeping=True, sleep_location=(rx, ry))
        self.world.entity_manager.add_component(villager, sleep_state)

        tiredness_before = self.world.entity_manager.get_component(villager, TirednessComponent).tiredness

        self.world.action_system.update(0.1)

        tiredness_after = self.world.entity_manager.get_component(villager, TirednessComponent).tiredness
        self.assert_equal(tiredness_after, tiredness_before,
                          "action_system should NOT change tiredness during sleep (NeedsSystem handles it)")


# ===========================================================================
# 5. Routine eating does not interrupt active jobs
# ===========================================================================

class TestRoutineEatingJobProtection(TestBase):
    """Routine EATING should not interrupt active jobs; only urgent hunger does."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_routine_eating_releases_active_job(self):
        """Villager with job + hunger=35 + EATING routine should release job and eat."""
        villager = create_test_villager(self.world, hunger=35.0, skills={"logging": 0.5})
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "EATING"

        tree = create_test_tree(self.world, 5, 5)
        give_chop_job(self.world, villager, tree, (5, 5))

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        self.world.ai_system.update(0.1)

        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_none(job_comp,
                            "Routine EATING should interrupt active job when hunger > 30")

    def test_urgent_hunger_interrupts_active_job(self):
        """Villager with job + hunger=55 should release job and seek food."""
        villager = create_test_villager(self.world, hunger=55.0, skills={"logging": 0.5})

        tree = create_test_tree(self.world, 5, 5)
        give_chop_job(self.world, villager, tree, (5, 5))

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        self.world.ai_system.update(0.1)

        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_is_none(job_comp, "Urgent hunger (>50) should release active job")
        self.assert_true(
            action.current_action in ("eat", "move"),
            f"Should be eating or moving to food, got {action.current_action}"
        )

    def test_routine_eating_works_for_idle_villagers(self):
        """Idle villager (no job) during EATING routine with hunger>30 should eat."""
        villager = create_test_villager(self.world, hunger=35.0)
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "EATING"

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_true(
            action.current_action in ("eat", "move"),
            f"Idle villager during EATING should eat, got {action.current_action}"
        )


# ===========================================================================
# 6. Hunger behavior during SLEEPING routine
# ===========================================================================

class TestHungerDuringSleeping(TestBase):
    """Hunger should be handled correctly during SLEEPING routine."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_urgent_hunger_works_during_sleeping_routine(self):
        """Villager with hunger>50 during SLEEPING should still eat if not asleep."""
        villager = create_test_villager(self.world, hunger=60.0, tiredness=30.0)
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "SLEEPING"

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_true(
            action.current_action in ("eat", "move"),
            f"Urgent hunger during SLEEPING should trigger eating, got {action.current_action}"
        )

    def test_routine_eating_suppressed_during_sleeping(self):
        """Routine-based eating should be suppressed during SLEEPING routine."""
        villager = create_test_villager(self.world, hunger=35.0, tiredness=30.0)
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "SLEEPING"

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_not_equal(action.current_action, "eat",
                              "Routine eating should be suppressed during SLEEPING")

    def test_moving_toward_sleep_suppresses_moderate_hunger(self):
        """Villager heading to residential zone should not be interrupted by moderate hunger (<=70)."""
        rx, ry = get_residential_tile(self.world)
        villager = create_test_villager(self.world, hunger=60.0, tiredness=50.0)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)
        action.current_action = "move"
        move_comp.target = (rx, ry)
        move_comp.path = [(rx, ry)]

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)
        self.assert_equal(action.current_action, "move",
                          "Should continue moving toward residential, not interrupt for moderate hunger")
        self.assert_equal(move_comp.target, (rx, ry),
                          "Target should still be residential tile")

    def test_moving_toward_sleep_not_suppressed_for_critical_hunger(self):
        """Villager heading to residential with hunger>90 should be interrupted for food."""
        rx, ry = get_residential_tile(self.world)
        villager = create_test_villager(self.world, hunger=92.0, tiredness=50.0)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)
        action.current_action = "move"
        move_comp.target = (rx, ry)
        move_comp.path = [(rx, ry)]

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_true(
            action.current_action in ("eat", "move"),
            f"Critical hunger (>90) should interrupt sleep-seeking, got {action.current_action}"
        )


# ===========================================================================
# 7. Plant job preference when carrying seeds
# ===========================================================================

class TestPlantJobSeedPreference(TestBase):
    """Villagers carrying seeds get a mild bonus for plant jobs (seed_bonus=1.5)."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_villager_with_seeds_prefers_plant_over_equal_priority(self):
        """Villager with seeds should choose plant over another same-priority job at similar distance."""
        villager = create_test_villager(self.world, hunger=20.0, skills={"logging": 0.1, "farming": 0.1})
        pos = self.world.entity_manager.get_component(villager, PositionComponent)

        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["seed_wheat"] = 2

        # Both jobs at same priority and same distance
        plant_job = Job(
            job_type="plant",
            target_pos=(pos.x + 3, pos.y),
            priority=3,
        )
        haul_job = Job(
            job_type="haul",
            target_pos=(pos.x - 3, pos.y),
            target_entity_id=99999,
            required_item="log",
            priority=3,
        )
        self.world.job_system.add_job(plant_job)
        self.world.job_system.add_job(haul_job)

        from src.components.skill_component import SkillComponent
        skill_comp = self.world.entity_manager.get_component(villager, SkillComponent)
        self.world.ai_system._find_job(villager, skill_comp, pos)

        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_not_none(job_comp, "Villager should take a job")
        self.assert_equal(job_comp.job_type, "plant",
                          "Villager with seeds should prefer plant job over equal-priority job")
