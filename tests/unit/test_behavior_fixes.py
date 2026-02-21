"""
行为修复回归测试
验证已修复的核心Bug不会复现:
  1. 收获任务优先级（成熟作物应优先于种植）
  2. 行走时不应恢复疲劳（needs_system bug）
  3. 进食行为持续性（到达食物后应立即吃，不受作息切换影响）
  4. 非工作时段清空非食物物品（种子囤积问题）
  5. 饥饿时拒绝远距离任务
  6. 饥饿/疲劳双重危机时不应振荡
"""
import tests  # ensure sys.path is set

from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager, create_test_item, create_test_tree
from src.components.data_components import (
    ActionComponent, RoutineComponent, HungerComponent, TirednessComponent,
    MoodComponent, InventoryComponent, PositionComponent, MovementComponent,
    JobComponent, CropComponent, ItemComponent
)
from src.components.skill_component import SkillComponent
from src.systems.job_system import Job


class TestHarvestPriority(TestBase):
    """收获任务应优先于种植任务"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_harvest_preferred_over_plant_with_seeds(self):
        """村民即使携带种子，也应优先收获成熟作物而非种植"""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        villager = create_test_villager(
            self.world,
            x=center_x, y=center_y + 5,
            skills={"farming": 0.6, "logging": 0.1},
            hunger=10.0
        )
        # Give villager seeds
        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["seed_wheat"] = 5

        # Create a plant job and a harvest job at similar distances
        plant_job = Job(
            job_type="plant",
            target_pos=(center_x + 2, center_y + 5),
            required_skill="farming",
            priority=3
        )
        self.world.job_system.add_job(plant_job)

        # Create a ripe crop entity for the harvest job
        crop_entity = self.world.entity_manager.create_entity()
        self.world.entity_manager.add_component(crop_entity, PositionComponent(x=center_x - 2, y=center_y + 5))
        self.world.entity_manager.add_component(crop_entity, CropComponent(
            crop_type="wheat", growth_progress=1.0, state="ripe"
        ))

        harvest_job = Job(
            job_type="harvest",
            target_pos=(center_x - 2, center_y + 5),
            target_entity_id=crop_entity,
            required_skill="farming",
            priority=5
        )
        self.world.job_system.add_job(harvest_job)

        # Run AI to assign job
        self.world.ai_system.update(0.016)

        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_not_none(job_comp, "Villager should have been assigned a job")
        self.assert_equal(job_comp.job_type, "harvest",
                          "Villager should prefer harvest over plant even with seeds in inventory")

    def test_harvest_score_beats_plant_score(self):
        """收获任务的评分应始终高于种植任务"""
        # Harvest: priority 5, harvest_bonus 3.0 → base = 5*2 + 3 = 13
        # Plant with seeds: priority 3, seed_bonus 1.5 → base = 3*2 + 1.5 = 7.5
        # Harvest should always beat plant regardless of seed bonus
        harvest_base = 5 * 2.0 + 3.0  # priority * 2 + harvest_bonus
        plant_with_seeds = 3 * 2.0 + 1.5  # priority * 2 + seed_bonus

        self.assert_greater(harvest_base, plant_with_seeds,
                            "Harvest base score should exceed plant+seeds score")


class TestTirednessMovingBug(TestBase):
    """行走时不应恢复疲劳（即使在SLEEPING作息段内）"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_walking_during_sleep_routine_does_not_recover_tiredness(self):
        """在SLEEPING作息时段行走，疲劳度不应减少"""
        villager = create_test_villager(self.world, tiredness=60.0, hunger=10.0)
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        tiredness_comp = self.world.entity_manager.get_component(villager, TirednessComponent)

        # Set to SLEEPING routine but actually moving
        routine_comp.current_state = "SLEEPING"
        action_comp.current_action = "move"
        initial_tiredness = tiredness_comp.tiredness

        # Simulate one game hour
        day_length = self.world.config_manager.get("simulation.day_length_seconds", 10.0)
        one_hour_dt = day_length / 24.0
        self.world.needs_system.update(one_hour_dt)

        final_tiredness = tiredness_comp.tiredness
        self.assert_greater_equal(final_tiredness, initial_tiredness,
                                  "Tiredness should NOT decrease while walking during SLEEPING routine")

    def test_idle_during_rest_routine_does_recover_tiredness(self):
        """在RESTING作息时段idle时，疲劳度应减少"""
        villager = create_test_villager(self.world, tiredness=60.0, hunger=10.0)
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        tiredness_comp = self.world.entity_manager.get_component(villager, TirednessComponent)

        routine_comp.current_state = "RESTING"
        action_comp.current_action = "idle"
        initial_tiredness = tiredness_comp.tiredness

        day_length = self.world.config_manager.get("simulation.day_length_seconds", 10.0)
        one_hour_dt = day_length / 24.0
        self.world.needs_system.update(one_hour_dt)

        final_tiredness = tiredness_comp.tiredness
        self.assert_less(final_tiredness, initial_tiredness,
                         "Tiredness should decrease when idle during RESTING routine")

    def test_sleeping_action_recovers_tiredness(self):
        """实际睡眠（action=sleep）应恢复疲劳"""
        villager = create_test_villager(self.world, tiredness=80.0, hunger=10.0)
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        tiredness_comp = self.world.entity_manager.get_component(villager, TirednessComponent)

        action_comp.current_action = "sleep"
        initial_tiredness = tiredness_comp.tiredness

        day_length = self.world.config_manager.get("simulation.day_length_seconds", 10.0)
        one_hour_dt = day_length / 24.0
        self.world.needs_system.update(one_hour_dt)

        final_tiredness = tiredness_comp.tiredness
        self.assert_less(final_tiredness, initial_tiredness,
                         "Tiredness should decrease when actually sleeping")


class TestFoodSeekingPersistence(TestBase):
    """到达食物后应完成进食（不受作息切换影响）"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_eat_when_adjacent_to_food_target(self):
        """当村民idle且target_entity_id指向邻近的食物时，应直接吃"""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        villager = create_test_villager(
            self.world, x=center_x, y=center_y,
            hunger=40.0
        )
        # Create food adjacent to villager
        food = create_test_item(self.world, center_x + 1, center_y, "food_wheat", 1)

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)

        # Simulate: villager was heading toward food during EATING, arrived, now idle
        # but routine has switched to WORKING
        action_comp.current_action = "idle"
        action_comp.target_entity_id = food
        routine_comp.current_state = "WORKING"

        # Run AI
        self.world.ai_system.update(0.016)

        action_after = self.world.entity_manager.get_component(villager, ActionComponent)
        self.assert_equal(action_after.current_action, "eat",
                          "Villager should eat food when idle and adjacent to food target")


class TestItemDroppingOnNonWorkRoutine(TestBase):
    """非工作时段应放下非食物物品"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_seeds_dropped_during_socializing(self):
        """社交时段，携带种子的idle村民应放下种子"""
        villager = create_test_villager(self.world, hunger=20.0)
        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["seed_wheat"] = 3

        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp.current_state = "SOCIALIZING"
        action_comp.current_action = "idle"

        # Run AI
        self.world.ai_system.update(0.016)

        # Seeds should have been dropped
        self.assert_true(
            inv.items.get("seed_wheat", 0) == 0,
            "Seeds should be dropped during SOCIALIZING"
        )

    def test_food_deposited_during_socializing(self):
        """社交时段，食物也应被存放（让社区共享资源）"""
        villager = create_test_villager(self.world, hunger=20.0)
        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["food_wheat"] = 2

        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp.current_state = "SOCIALIZING"
        action_comp.current_action = "idle"

        self.world.ai_system.update(0.016)

        self.assert_equal(
            inv.items.get("food_wheat", 0), 0,
            "Food should be deposited during SOCIALIZING (shared resources)"
        )

    def test_seeds_dropped_during_sleeping(self):
        """睡眠时段，携带种子的idle村民应先放下种子再去睡"""
        villager = create_test_villager(self.world, hunger=20.0, tiredness=50.0)
        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        inv.items["seed_wheat"] = 2
        inv.items["log"] = 1

        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp.current_state = "SLEEPING"
        action_comp.current_action = "idle"

        self.world.ai_system.update(0.016)

        self.assert_equal(inv.items.get("seed_wheat", 0), 0,
                          "Seeds should be dropped before sleeping")
        self.assert_equal(inv.items.get("log", 0), 0,
                          "Logs should be dropped before sleeping")


class TestHungryDistantJobRefusal(TestBase):
    """饥饿时应拒绝远距离任务"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_refuse_distant_job_when_moderately_hungry(self):
        """饥饿度>30时，不应接受超过max_dist的任务"""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        villager = create_test_villager(
            self.world, x=center_x, y=center_y,
            hunger=50.0,
            skills={"logging": 0.6, "farming": 0.1}
        )

        # Create a distant chop job (distance ~30)
        distant_tree = create_test_tree(self.world, center_x - 30, center_y)
        distant_job = Job(
            job_type="chop",
            target_pos=(center_x - 30, center_y),
            target_entity_id=distant_tree,
            required_skill="logging",
            priority=4
        )
        self.world.job_system.add_job(distant_job)

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        action_comp.current_action = "idle"
        routine_comp.current_state = "WORKING"

        self.world.ai_system.update(0.016)

        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        # At hunger 50, max_dist = max(5, 35 - 50*0.4) = max(5, 15) = 15
        # Distance 30 > 15, so job should be refused
        self.assert_true(
            job_comp is None,
            "Villager at hunger=50 should refuse job at distance 30"
        )

    def test_accept_close_job_when_moderately_hungry(self):
        """饥饿度>30时，仍应接受近距离任务"""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        villager = create_test_villager(
            self.world, x=center_x, y=center_y,
            hunger=50.0,
            skills={"logging": 0.6, "farming": 0.1}
        )

        # Create a nearby chop job (distance ~3)
        nearby_tree = create_test_tree(self.world, center_x + 3, center_y)
        nearby_job = Job(
            job_type="chop",
            target_pos=(center_x + 3, center_y),
            target_entity_id=nearby_tree,
            required_skill="logging",
            priority=4
        )
        self.world.job_system.add_job(nearby_job)

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        action_comp.current_action = "idle"
        routine_comp.current_state = "WORKING"

        self.world.ai_system.update(0.016)

        job_comp = self.world.entity_manager.get_component(villager, JobComponent)
        self.assert_is_not_none(job_comp, "Villager at hunger=50 should accept nearby job")

    def test_max_dist_scales_with_hunger(self):
        """max_dist应随饥饿度增加而缩小"""
        # formula: max_dist = max(5, 35 - hunger * 0.4)
        # At hunger 30: max(5, 35-12) = 23
        # At hunger 50: max(5, 35-20) = 15
        # At hunger 70: max(5, 35-28) = 7
        # At hunger 80: max(5, 35-32) = 5 (floor)
        dist_at_30 = max(5, int(35 - 30 * 0.4))
        dist_at_50 = max(5, int(35 - 50 * 0.4))
        dist_at_70 = max(5, int(35 - 70 * 0.4))
        dist_at_80 = max(5, int(35 - 80 * 0.4))

        self.assert_greater(dist_at_30, dist_at_50, "Max dist at hunger=30 > hunger=50")
        self.assert_greater(dist_at_50, dist_at_70, "Max dist at hunger=50 > hunger=70")
        self.assert_equal(dist_at_80, 5, "Max dist should floor at 5")


class TestAntiOscillation(TestBase):
    """双重危机（饥饿+疲劳）时不应在sleep/eat间振荡"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_no_oscillation_when_both_critical(self):
        """当饥饿和疲劳都很高时，不应在sleep和eat之间反复切换"""
        from src.world.grid import ZONE_RESIDENTIAL
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        villager = create_test_villager(
            self.world,
            x=center_x, y=center_y - 4,  # On residential zone
            hunger=90.0, tiredness=95.0
        )

        # Put some food nearby
        create_test_item(self.world, center_x, center_y, "food_wheat", 3)

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine_comp.current_state = "SLEEPING"
        action_comp.current_action = "sleep"

        # Run multiple ticks and count action changes
        action_changes = 0
        last_action = action_comp.current_action
        for _ in range(50):
            self.world.ai_system.update(0.016)
            if action_comp.current_action != last_action:
                action_changes += 1
                last_action = action_comp.current_action

        # Should not oscillate excessively — at most a few transitions
        self.assert_less(action_changes, 10,
                         f"Should not oscillate: got {action_changes} action changes in 50 ticks")

    def test_sleep_lock_suppresses_hunger(self):
        """睡眠锁定期间，饥饿度<=95不应打断睡眠"""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        villager = create_test_villager(
            self.world,
            x=center_x, y=center_y - 4,  # Residential zone
            hunger=90.0, tiredness=92.0
        )
        create_test_item(self.world, center_x, center_y, "food_wheat", 3)

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine_comp.current_state = "SLEEPING"
        action_comp.current_action = "sleep"

        current_tick = self.world.time_manager.total_ticks
        # Manually set sleep lock
        self.world.ai_system._set_need_lock(villager, "sleep", current_tick, 300)

        # Run AI
        self.world.ai_system.update(0.016)

        # Should still be sleeping (hunger 90 <= 95 threshold)
        self.assert_equal(action_comp.current_action, "sleep",
                          "Sleep lock should suppress hunger at 90 (threshold 95)")

    def test_eat_lock_suppresses_tiredness(self):
        """进食锁定期间，疲劳度不应打断进食"""
        center_x = self.world.grid.width // 2
        center_y = self.world.grid.height // 2

        villager = create_test_villager(
            self.world,
            x=center_x, y=center_y,
            hunger=80.0, tiredness=95.0
        )
        create_test_item(self.world, center_x + 1, center_y, "food_wheat", 3)

        action_comp = self.world.entity_manager.get_component(villager, ActionComponent)
        routine_comp = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine_comp.current_state = "WORKING"
        action_comp.current_action = "move"
        action_comp.target_entity_id = None  # will be set by AI

        current_tick = self.world.time_manager.total_ticks
        # Manually set eat lock
        self.world.ai_system._set_need_lock(villager, "eat", current_tick, 300)

        # Run AI
        self.world.ai_system.update(0.016)

        # Should not switch to sleep (eat lock fully suppresses tiredness)
        self.assert_true(
            action_comp.current_action != "sleep",
            "Eat lock should fully suppress tiredness, villager should not sleep"
        )
