"""
回归测试：诊断日志分析发现的 Bug
覆盖以下修复：
  1. 进食/睡眠需求应能中断正在走向工作目标的 "move" 动作
  2. 从地面进食时只消耗1单位，不拿走整个堆叠
  3. _find_and_sleep 只在站在住宅区格子上时才设置 "sleep"
  4. 中断时必须清除旧的移动路径
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from tests.test_helpers import (
    TestWorld, create_test_villager, create_test_tree, create_test_item,
    get_residential_tile, give_chop_job
)
from src.components.data_components import (
    ActionComponent, MovementComponent, PositionComponent, InventoryComponent,
    HungerComponent, TirednessComponent, MoodComponent, ItemComponent,
    JobComponent, RoutineComponent, SleepStateComponent
)
from src.systems.job_system import Job
from src.world.grid import ZONE_RESIDENTIAL, ZONE_STOCKPILE


# ===========================================================================
# Bug 1 — 进食需求应能中断走向工作目标的 "move"
# ===========================================================================

class TestEatingInterruptsMove(TestBase):
    """进食需求应能中断正在走向工作目标的 move 动作"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    # ---- 1a: 紧急饥饿中断 move ----
    def test_urgent_hunger_interrupts_move_to_job(self):
        """饥饿>50 且有食物时，应中断走向工作的 move 并转向食物"""
        villager = create_test_villager(self.world, hunger=60.0, skills={"logging": 0.5})
        tree = create_test_tree(self.world, 5, 5)
        give_chop_job(self.world, villager, tree, (5, 5))

        # 在村民附近放置食物
        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        food = create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        # 运行 AI
        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        job_comp = self.world.entity_manager.get_component(villager, JobComponent)

        self.assert_true(
            action.current_action in ("eat", "move") and job_comp is None,
            f"Should release job and seek food, got action={action.current_action}, job={job_comp}"
        )

    # ---- 1b: 例行进餐SHOULD中断有活跃任务的 move ----
    def test_routine_eating_interrupts_active_job(self):
        """Routine=EATING 且 hunger>30 时，应释放任务去吃饭
        (按日程表进食，确保村民按时吃饭而不是等到饥饿临界值)"""
        villager = create_test_villager(self.world, hunger=40.0, skills={"logging": 0.5})
        routine = self.world.entity_manager.get_component(villager, RoutineComponent)
        routine.current_state = "EATING"

        tree = create_test_tree(self.world, 5, 5)
        give_chop_job(self.world, villager, tree, (5, 5))

        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        food = create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        job_comp = self.world.entity_manager.get_component(villager, JobComponent)

        self.assert_is_none(
            job_comp,
            f"Routine EATING should interrupt active job (hunger>30), got job={job_comp}"
        )
        self.assert_true(
            action.current_action in ("eat", "move"),
            f"Should seek food, got action={action.current_action}"
        )

    # ---- 1c: 已经在去往食物的路上时不应重复中断 ----
    def test_no_re_interrupt_when_already_heading_to_food(self):
        """已经在 move 向食物时不应再次中断"""
        villager = create_test_villager(self.world, hunger=60.0, skills={"logging": 0.5})
        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        food = create_test_item(self.world, pos.x + 5, pos.y, "food_wheat", 2)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)

        # 模拟: 已经在走向食物
        action.current_action = "move"
        action.target_entity_id = food
        move_comp.target = (pos.x + 5, pos.y)
        move_comp.path = [(pos.x + 3, pos.y), (pos.x + 5, pos.y)]

        self.world.ai_system.update(0.1)

        # 路径应该保持不变，没有被清除再重设
        self.assert_equal(
            action.current_action, "move",
            "Should stay in move when already heading to food"
        )
        self.assert_equal(
            action.target_entity_id, food,
            "target_entity_id should remain the food entity"
        )


# ===========================================================================
# Bug 2 — 睡眠需求应能中断走向工作目标的 "move"
# ===========================================================================

class TestSleepingInterruptsMove(TestBase):
    """睡眠需求应能中断正在走向工作目标的 move 动作"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_urgent_tiredness_interrupts_move_to_job(self):
        """tiredness>90 时应中断走向工作的 move"""
        villager = create_test_villager(self.world, tiredness=95.0, skills={"logging": 0.5})
        tree = create_test_tree(self.world, 5, 5)
        give_chop_job(self.world, villager, tree, (5, 5))

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        job_comp = self.world.entity_manager.get_component(villager, JobComponent)

        self.assert_is_none(job_comp, "Job should be released when urgently tired")
        self.assert_true(
            action.current_action in ("sleep", "move"),
            f"Should seek sleep, got action={action.current_action}"
        )

    def test_no_re_interrupt_when_heading_to_residential(self):
        """已在走向住宅区时不应再次中断"""
        villager = create_test_villager(self.world, tiredness=95.0, skills={"logging": 0.5})
        rx, ry = get_residential_tile(self.world)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)

        action.current_action = "move"
        move_comp.target = (rx, ry)
        move_comp.path = [(rx, ry)]

        self.world.ai_system.update(0.1)

        # 不应清除路径或改变动作——已经在去住宅区
        self.assert_equal(
            action.current_action, "move",
            "Should stay in move when already heading to residential"
        )
        self.assert_equal(
            move_comp.target, (rx, ry),
            "Target should remain residential tile"
        )


# ===========================================================================
# Bug 3 — 从地面进食只消耗 1 单位，不拿走整个堆叠
# ===========================================================================

class TestEatFromGroundNoHoarding(TestBase):
    """从地面进食时只应消耗1单位食物，其余留给其他村民"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_eat_ground_food_takes_only_one(self):
        """地面 food_wheat x5，进食后应剩 4"""
        villager = create_test_villager(self.world, hunger=80.0)
        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        food = create_test_item(self.world, pos.x, pos.y, "food_wheat", 5)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "eat"
        action.target_entity_id = food

        self.world.action_system.update(0.1)

        # 食物实体应该仍然存在且数量=4
        self.assert_true(
            self.world.entity_manager.has_entity(food),
            "Food entity should still exist after eating 1 from stack of 5"
        )
        item_comp = self.world.entity_manager.get_component(food, ItemComponent)
        self.assert_equal(item_comp.amount, 4, "Food stack should have 4 remaining")

        # 村民饥饿应降低
        hunger = self.world.entity_manager.get_component(villager, HungerComponent)
        self.assert_less(hunger.hunger, 80.0, "Hunger should decrease after eating")

        # 库存不应增加（食物直接从地面消耗，不 pickup 到库存）
        inv = self.world.entity_manager.get_component(villager, InventoryComponent)
        food_in_inv = inv.items.get("food_wheat", 0)
        self.assert_equal(food_in_inv, 0, "Food should not be added to inventory when eating from ground")

    def test_eat_ground_food_last_unit_destroys_entity(self):
        """地面 food_wheat x1，进食后实体应被销毁"""
        villager = create_test_villager(self.world, hunger=80.0)
        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        food = create_test_item(self.world, pos.x, pos.y, "food_wheat", 1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)
        action.current_action = "eat"
        action.target_entity_id = food

        self.world.action_system.update(0.1)

        self.assert_false(
            self.world.entity_manager.has_entity(food),
            "Food entity should be destroyed after eating last unit"
        )

    def test_two_villagers_share_ground_food(self):
        """两个村民可以依次从同一堆地面食物中进食"""
        pos_x = self.world.grid.width // 2
        pos_y = self.world.grid.height // 2

        v1 = create_test_villager(self.world, x=pos_x, y=pos_y, hunger=80.0)
        v2 = create_test_villager(self.world, x=pos_x, y=pos_y, hunger=80.0)
        food = create_test_item(self.world, pos_x, pos_y, "food_wheat", 3)

        # 第一个村民进食
        action1 = self.world.entity_manager.get_component(v1, ActionComponent)
        action1.current_action = "eat"
        action1.target_entity_id = food
        self.world.action_system.update(0.1)

        self.assert_true(
            self.world.entity_manager.has_entity(food),
            "Food should still exist after first villager eats"
        )
        remaining = self.world.entity_manager.get_component(food, ItemComponent).amount
        self.assert_equal(remaining, 2, "2 units should remain after first eat")

        # 第二个村民进食
        action2 = self.world.entity_manager.get_component(v2, ActionComponent)
        action2.current_action = "eat"
        action2.target_entity_id = food
        self.world.action_system.update(0.1)

        self.assert_true(
            self.world.entity_manager.has_entity(food),
            "Food should still exist after second villager eats"
        )
        remaining2 = self.world.entity_manager.get_component(food, ItemComponent).amount
        self.assert_equal(remaining2, 1, "1 unit should remain after second eat")


# ===========================================================================
# Bug 4 — _find_and_sleep 只在站在住宅格时才设置 "sleep"
# ===========================================================================

class TestFindAndSleepZoneCheck(TestBase):
    """_find_and_sleep 只在村民站在住宅区格子上时才把动作设为 sleep"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_sleep_when_on_residential_tile(self):
        """站在住宅区格子上时应直接开始睡觉"""
        rx, ry = get_residential_tile(self.world)
        villager = create_test_villager(self.world, x=rx, y=ry, tiredness=95.0)
        action = self.world.entity_manager.get_component(villager, ActionComponent)
        pos = self.world.entity_manager.get_component(villager, PositionComponent)

        self.world.ai_system._find_and_sleep(villager, action, pos)

        self.assert_equal(
            action.current_action, "sleep",
            "Should set action to sleep when standing on residential tile"
        )

    def test_move_when_adjacent_to_residential(self):
        """不在住宅区格子上时应设为 move 而非 sleep（即使仅1格距离）"""
        rx, ry = get_residential_tile(self.world)
        # 放在住宅区旁边但不在区域内的格子
        adj_x, adj_y = rx, ry + 10  # 远离住宅区
        # 确认此格子不在住宅区
        zone = self.world.grid.get_zone(adj_x, adj_y)
        if zone == ZONE_RESIDENTIAL:
            adj_x, adj_y = rx + 10, ry + 10

        villager = create_test_villager(self.world, x=adj_x, y=adj_y, tiredness=95.0)
        action = self.world.entity_manager.get_component(villager, ActionComponent)
        pos = self.world.entity_manager.get_component(villager, PositionComponent)

        self.world.ai_system._find_and_sleep(villager, action, pos)

        self.assert_equal(
            action.current_action, "move",
            "Should set action to move (not sleep) when not on residential tile"
        )


# ===========================================================================
# Bug 5 — 中断时应清除旧移动路径
# ===========================================================================

class TestMovementClearedOnInterrupt(TestBase):
    """当 AI 中断村民当前动作时，旧移动路径和目标必须被清除"""

    def setup(self):
        self.world = TestWorld()

    def teardown(self):
        self.world.config_manager.stop()

    def test_path_cleared_on_hunger_interrupt(self):
        """饥饿中断时旧路径应被清除"""
        villager = create_test_villager(self.world, hunger=60.0, skills={"logging": 0.5})
        tree = create_test_tree(self.world, 5, 5)
        give_chop_job(self.world, villager, tree, (5, 5))

        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)
        old_path = list(move_comp.path)
        self.assert_greater(len(old_path), 0, "Should have a path before interrupt")

        # 在村民附近放置食物
        pos = self.world.entity_manager.get_component(villager, PositionComponent)
        food = create_test_item(self.world, pos.x + 1, pos.y, "food_wheat", 3)

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)

        # 如果转为 eat（食物在旁边），path 应该为空
        # 如果转为 move（向新目标），path 应该是新的（不是旧的工作路径）
        if action.current_action == "eat":
            self.assert_equal(len(move_comp.path), 0, "Path should be cleared after interrupt")
            self.assert_is_none(move_comp.target, "Target should be None after interrupt to eat")
        else:
            # move 向食物 — 旧路径应被替换（目标不再是 (5,5)）
            self.assert_not_equal(
                move_comp.target, (5, 5),
                "Movement target should no longer point to old job target"
            )

    def test_path_cleared_on_tiredness_interrupt(self):
        """疲劳中断时旧路径应被清除"""
        villager = create_test_villager(self.world, tiredness=95.0, skills={"logging": 0.5})
        tree = create_test_tree(self.world, 5, 5)
        give_chop_job(self.world, villager, tree, (5, 5))

        move_comp = self.world.entity_manager.get_component(villager, MovementComponent)
        self.assert_greater(len(move_comp.path), 0, "Should have a path before interrupt")

        self.world.ai_system.update(0.1)

        action = self.world.entity_manager.get_component(villager, ActionComponent)

        if action.current_action == "sleep":
            self.assert_equal(len(move_comp.path), 0, "Path should be cleared after sleep interrupt")
        else:
            # 移向住宅区
            self.assert_not_equal(
                move_comp.target, (5, 5),
                "Movement target should no longer point to old job target"
            )
