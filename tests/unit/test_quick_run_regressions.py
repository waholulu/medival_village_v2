"""
Quick-run regression tests for bugs found during --quick mode analysis.

Covers:
  1. Movement speed is sufficient for villagers to traverse map in reasonable time
  2. Chop job generation respects max_chop_jobs limit (counter bug)
  3. Food haul jobs have higher priority than non-food hauls
  4. JobSystem.complete_job increments the diagnostic jobs_completed counter
  5. Villagers can actually chop a tree within a reasonable number of ticks
  6. Villagers can reach residential zone and enter sleep within sleep hours
"""
import tests  # ensure tests/__init__.py sys.path setup

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_tree, create_test_item
from src.components.data_components import (
    ActionComponent, PositionComponent, MovementComponent, HungerComponent,
    TirednessComponent, JobComponent, RoutineComponent, SleepStateComponent,
    ItemComponent, ResourceComponent
)
from src.components.tags import IsTree
from src.systems.job_system import Job


class TestMovementSpeed(TestBase):
    """Verify move speed allows traversal in reasonable game time."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_villager_moves_one_tile_within_15_ticks(self):
        """A villager should move 1 tile in well under 30 ticks (< ~30 game-min)."""
        villager = create_test_villager(self.world, x=10, y=10, hunger=0.0, tiredness=0.0)

        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)

        move_comp.target = (11, 10)
        action_comp.current_action = "move"

        dt = 1.0 / self.world.time_manager.tick_rate
        ticks = 0
        max_ticks = 30

        for _ in range(max_ticks):
            self.world.action_system.update(dt)
            ticks += 1
            pos = self.world.entity_manager.get_component(villager, PositionComponent)
            if pos.x == 11 and pos.y == 10:
                break

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        self.assert_equal(pos.x, 11, f"Villager should reach x=11 within {max_ticks} ticks, took {ticks}")
        self.assert_less(ticks, 20, f"Should move 1 tile quickly, took {ticks} ticks")

    def test_villager_traverses_10_tiles_within_150_ticks(self):
        """10 tiles should take roughly 100 ticks (~100 game-min ~ 1.7 hrs) at most."""
        villager = create_test_villager(self.world, x=5, y=10, hunger=0.0, tiredness=0.0)

        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)

        move_comp.target = (15, 10)
        action_comp.current_action = "move"

        dt = 1.0 / self.world.time_manager.tick_rate
        ticks = 0
        max_ticks = 150

        for _ in range(max_ticks):
            self.world.action_system.update(dt)
            ticks += 1
            pos = self.world.entity_manager.get_component(villager, PositionComponent)
            if pos.x == 15 and pos.y == 10:
                break

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        self.assert_equal(pos.x, 15, f"Villager should reach x=15 within {max_ticks} ticks, took {ticks}")


class TestChopJobGenerationLimit(TestBase):
    """Chop job generation must respect the max_chop_jobs cap."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_chop_jobs_capped_at_max(self):
        """Creating many trees should NOT create more than max_chop_jobs (10) chop jobs."""
        # Place 30 trees
        for i in range(30):
            x = 5 + (i % 10)
            y = 5 + (i // 10)
            tree = create_test_tree(self.world, x, y)

        # Ensure job gen fires
        self.world.ai_system._last_job_gen_tick = -10
        self.world.time_manager.total_ticks = 10

        self.world.ai_system._generate_jobs()

        chop_jobs = [j for j in self.world.job_system.jobs if j.job_type == "chop"]

        # The cap is 10 (max_chop_jobs in ai_system._generate_jobs)
        self.assert_less_equal(
            len(chop_jobs), 10,
            f"Chop jobs should be capped at 10, got {len(chop_jobs)}"
        )
        self.assert_greater(len(chop_jobs), 0, "Should have created at least 1 chop job")

    def test_chop_jobs_incremental_generation(self):
        """After completing some chop jobs, new ones should be created up to the cap."""
        # Place 20 trees
        trees = []
        for i in range(20):
            x = 5 + (i % 10)
            y = 5 + (i // 10)
            trees.append(create_test_tree(self.world, x, y))

        # First generation
        self.world.ai_system._last_job_gen_tick = -10
        self.world.time_manager.total_ticks = 10
        self.world.ai_system._generate_jobs()

        first_count = sum(1 for j in self.world.job_system.jobs if j.job_type == "chop")
        self.assert_less_equal(first_count, 10, "First batch capped at 10")

        # Complete 5 chop jobs
        chop_jobs = [j for j in self.world.job_system.jobs if j.job_type == "chop"]
        for job in chop_jobs[:5]:
            self.world.job_system.complete_job(job.id)

        remaining = sum(1 for j in self.world.job_system.jobs if j.job_type == "chop")
        self.assert_equal(remaining, first_count - 5, "5 jobs should have been removed")

        # Trigger second generation
        self.world.ai_system._last_job_gen_tick = -10
        self.world.time_manager.total_ticks = 30
        self.world.ai_system._generate_jobs()

        after_regen = sum(1 for j in self.world.job_system.jobs if j.job_type == "chop")
        self.assert_less_equal(after_regen, 10, f"After regen, still capped at 10, got {after_regen}")
        self.assert_greater(after_regen, remaining, "New chop jobs should have been created")


class TestFoodHaulPriority(TestBase):
    """Food haul jobs should have higher priority than non-food haul jobs."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_food_haul_has_higher_priority_than_seed_haul(self):
        """food_wheat haul should have priority 5, seed_wheat should have priority 2."""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        # Place items outside stockpile
        food_item = create_test_item(self.world, center_x + 10, center_y + 10, "food_wheat", 2)
        seed_item = create_test_item(self.world, center_x + 10, center_y + 11, "seed_wheat", 3)

        self.world.ai_system._last_job_gen_tick = -10
        self.world.time_manager.total_ticks = 10
        self.world.ai_system._generate_jobs()

        haul_jobs = [j for j in self.world.job_system.jobs if j.job_type == "haul"]

        food_haul = None
        seed_haul = None
        for j in haul_jobs:
            if j.required_item == "food_wheat":
                food_haul = j
            elif j.required_item == "seed_wheat":
                seed_haul = j

        self.assert_is_not_none(food_haul, "Should create haul job for food_wheat")
        self.assert_is_not_none(seed_haul, "Should create haul job for seed_wheat")
        self.assert_greater(
            food_haul.priority, seed_haul.priority,
            f"Food haul priority ({food_haul.priority}) should be > seed haul ({seed_haul.priority})"
        )

    def test_villager_prefers_food_haul_over_chop(self):
        """When both food haul and chop jobs exist, a villager should prefer food haul
        because food haul priority (5) > chop priority (4)."""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        villager = create_test_villager(
            self.world, x=center_x + 8, y=center_y + 8,
            skills={"logging": 0.5, "farming": 0.5},
            hunger=10.0
        )

        # Create food on ground (outside stockpile)
        food_item = create_test_item(self.world, center_x + 9, center_y + 9, "food_wheat", 5)

        # Also create a tree nearby
        tree = create_test_tree(self.world, center_x + 7, center_y + 7)

        # Generate jobs
        self.world.ai_system._last_job_gen_tick = -10
        self.world.time_manager.total_ticks = 10
        self.world.ai_system._generate_jobs()

        # Now let AI assign job to idle villager
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        action_comp.current_action = "idle"

        # Set routine to WORKING
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "WORKING"

        self.world.ai_system.update(0.1)

        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_not_none(job_comp, "Villager should have taken a job")
        self.assert_equal(job_comp.job_type, "haul", f"Should prefer food haul, got {job_comp.job_type}")


class TestJobCompletedCounter(TestBase):
    """JobSystem.complete_job should track completions in DiagnosticLogger."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        # Clean up diagnostic logger singleton
        from src.utils.diagnostic_logger import DiagnosticLogger
        DiagnosticLogger._instance = None
        self.world.config_manager.stop()

    def test_complete_job_increments_counter(self):
        """Each call to complete_job should increment the jobs_completed counter."""
        from src.utils.diagnostic_logger import DiagnosticLogger, DayStats

        # Set up a minimal diagnostic logger
        diag = DiagnosticLogger(self.world.entity_manager, self.world.time_manager)
        diag._enabled = True
        diag._day_stats = DayStats()

        # Suppress file writing for tests
        import io
        diag._summary_file = io.StringIO()
        diag._detail_file = io.StringIO()

        initial = diag._day_stats.jobs_completed

        # Create and complete a job
        job = Job(job_type="chop", target_pos=(5, 5), priority=1)
        self.world.job_system.add_job(job)
        self.world.job_system.complete_job(job.id)

        self.assert_equal(
            diag._day_stats.jobs_completed, initial + 1,
            "jobs_completed should increment by 1"
        )

        # Complete another
        job2 = Job(job_type="haul", target_pos=(6, 6), priority=2)
        self.world.job_system.add_job(job2)
        self.world.job_system.complete_job(job2.id)

        self.assert_equal(
            diag._day_stats.jobs_completed, initial + 2,
            "jobs_completed should increment by 2 total"
        )

    def test_complete_nonexistent_job_no_crash(self):
        """Completing a non-existent job should not crash or increment counter."""
        from src.utils.diagnostic_logger import DiagnosticLogger, DayStats

        diag = DiagnosticLogger(self.world.entity_manager, self.world.time_manager)
        diag._enabled = True
        diag._day_stats = DayStats()

        import io
        diag._summary_file = io.StringIO()
        diag._detail_file = io.StringIO()

        initial = diag._day_stats.jobs_completed
        self.world.job_system.complete_job("nonexistent-uuid")

        self.assert_equal(
            diag._day_stats.jobs_completed, initial,
            "Should not increment for non-existent job"
        )


class TestTreeChoppingSpeed(TestBase):
    """A villager adjacent to a tree should chop it in reasonable time."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_skilled_villager_chops_tree_under_30_ticks(self):
        """V0-equivalent (logging=0.6) should chop a tree (HP=20) in ~19 ticks, well under 30."""
        tree = create_test_tree(self.world, 10, 10, health=20)
        villager = create_test_villager(
            self.world, x=11, y=10,
            skills={"logging": 0.6},
            hunger=0.0, tiredness=0.0
        )

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        action_comp.current_action = "chop"
        action_comp.target_entity_id = tree

        dt = 1.0 / self.world.time_manager.tick_rate
        ticks = 0
        max_ticks = 40

        for _ in range(max_ticks):
            self.world.action_system.update(dt)
            ticks += 1
            if not self.world.entity_manager.has_entity(tree):
                break

        self.assert_false(
            self.world.entity_manager.has_entity(tree),
            f"Tree should be destroyed within {max_ticks} ticks (took {ticks})"
        )
        self.assert_less(ticks, 30, f"Skilled villager should chop tree quickly, took {ticks}")

    def test_unskilled_villager_chops_tree_under_50_ticks(self):
        """V2-equivalent (logging=0.1) should chop a tree (HP=20) in ~30 ticks, under 50."""
        tree = create_test_tree(self.world, 10, 10, health=20)
        villager = create_test_villager(
            self.world, x=11, y=10,
            skills={"logging": 0.1},
            hunger=0.0, tiredness=0.0
        )

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        action_comp.current_action = "chop"
        action_comp.target_entity_id = tree

        dt = 1.0 / self.world.time_manager.tick_rate
        ticks = 0
        max_ticks = 60

        for _ in range(max_ticks):
            self.world.action_system.update(dt)
            ticks += 1
            if not self.world.entity_manager.has_entity(tree):
                break

        self.assert_false(
            self.world.entity_manager.has_entity(tree),
            f"Tree should be destroyed within {max_ticks} ticks (took {ticks})"
        )
        self.assert_less(ticks, 50, f"Even unskilled villager should finish, took {ticks}")


class TestSleepBehavior(TestBase):
    """Villagers should reach residential and enter sleep during SLEEPING routine."""

    def setup(self):
        self.world = TestWorld()
        # Residential zone is at center_x-2..+2, center_y-6..center_y-3
        # i.e. x:[18,19,20,21], y:[9,10,11] for 40x30 map

    def teardown(self):
        self.world.config_manager.stop()

    def test_villager_starts_sleep_on_residential_tile(self):
        """If already on residential during SLEEPING routine, should enter sleep."""
        center_x = self.world.grid.width // 2   # 20
        center_y = self.world.grid.height // 2   # 15

        # Place villager inside residential zone
        res_x = center_x - 1  # 19
        res_y = center_y - 5  # 10
        villager = create_test_villager(
            self.world, x=res_x, y=res_y,
            hunger=20.0, tiredness=50.0
        )

        # Set routine to SLEEPING
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "SLEEPING"

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        action_comp.current_action = "idle"

        # Run AI — should trigger _find_and_sleep → detect residential → sleep
        self.world.ai_system.update(0.1)

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_equal(
            action_comp.current_action, "sleep",
            f"Villager on residential during SLEEPING should sleep, got {action_comp.current_action}"
        )

    def test_villager_navigates_to_residential_for_sleep(self):
        """A villager NOT on residential should navigate there during SLEEPING."""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        # Place villager away from residential
        villager = create_test_villager(
            self.world, x=center_x, y=center_y,
            hunger=20.0, tiredness=50.0
        )

        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "SLEEPING"

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        action_comp.current_action = "idle"

        self.world.ai_system.update(0.1)

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)

        self.assert_equal(
            action_comp.current_action, "move",
            f"Should start moving to residential, got {action_comp.current_action}"
        )
        self.assert_is_not_none(move_comp.target, "Should have a movement target set")

    def test_villager_enters_sleep_after_reaching_residential(self):
        """After moving to residential zone, the villager should eventually sleep."""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        # Place villager a few tiles away from residential
        villager = create_test_villager(
            self.world, x=center_x, y=center_y,
            hunger=10.0, tiredness=50.0
        )

        # Set time to sleep hours (22:00)
        self.world.time_manager.time_of_day = 22.0

        dt = 1.0 / self.world.time_manager.tick_rate
        max_ticks = 200
        entered_sleep = False

        for _ in range(max_ticks):
            self.world.update(dt)
            action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
            if action_comp.current_action == "sleep":
                entered_sleep = True
                break

        self.assert_true(entered_sleep, "Villager should enter sleep after reaching residential")


class TestHaulDropsOnStockpile(TestBase):
    """Hauled items must be dropped ON stockpile tiles, not adjacent to them."""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_haul_drops_item_inside_stockpile_zone(self):
        """After hauling, the dropped item should be inside the stockpile zone."""
        from src.world.grid import ZONE_STOCKPILE
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        # Place log far from stockpile
        log_item = create_test_item(self.world, center_x + 10, center_y, "log", 1)

        villager = create_test_villager(
            self.world, x=center_x + 10, y=center_y,
            skills={"logging": 0.5},
            hunger=0.0, tiredness=0.0
        )

        self.world.time_manager.time_of_day = 10.0

        dt = 1.0 / self.world.time_manager.tick_rate
        log_in_stockpile = False

        for _ in range(400):
            self.world.time_manager.time_of_day = 10.0
            self.world.update(dt)

            # Check if any log is in stockpile zone
            for _, item_comp, pos in self.world.entity_manager.get_entities_with(ItemComponent, PositionComponent):
                if item_comp.item_type == "log":
                    zone = self.world.grid.get_zone(pos.x, pos.y)
                    if zone == ZONE_STOCKPILE:
                        log_in_stockpile = True
                        break
            if log_in_stockpile:
                break

        self.assert_true(
            log_in_stockpile,
            "Hauled log should end up ON a stockpile tile, not adjacent"
        )
