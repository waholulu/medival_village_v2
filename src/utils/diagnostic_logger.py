"""
Two-tier diagnostic logging system for villager behavior analysis.

Tier 1 (SUMMARY): Key events only - routine changes, job outcomes, critical alerts, periodic snapshots.
Tier 2 (DETAIL):  Everything in summary + AI reasoning, exact numeric changes, inventory deltas, all thresholds.

Usage:
    python main.py --diagnostic
    python main.py --headless --diagnostic
"""

import datetime
import os
import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, Any


class DiagLevel(Enum):
    SUMMARY = 1  # Goes to BOTH files
    DETAIL = 2   # Goes to detail file ONLY


@dataclass
class VillagerStateCache:
    """Cached state for change detection."""
    action: str = "idle"
    routine_state: str = ""
    job_type: Optional[str] = None
    job_id: Optional[str] = None
    is_sleeping: bool = False
    inventory_snapshot: Dict[str, int] = field(default_factory=dict)
    # Need brackets: hunger [0-30, 30-50, 50-80, 80-100]
    hunger_bracket: int = 0
    # Tiredness brackets: [0-50, 50-90, 90-100]
    tiredness_bracket: int = 0
    # Mood brackets: [0-30, 30-70, 70-100]
    mood_bracket: int = 0
    # Cold brackets: [0-30, 30-60, 60-100]
    cold_bracket: int = 0


@dataclass
class DayStats:
    """Aggregated stats for end-of-day summary."""
    food_consumed: int = 0
    jobs_completed: int = 0
    trees_chopped: int = 0
    crops_harvested: int = 0
    fish_caught: int = 0
    traps_caught: int = 0
    resources_gathered: Dict[str, int] = field(default_factory=dict)
    hunger_warnings: int = 0
    tiredness_warnings: int = 0
    mood_warnings: int = 0
    cold_damage_events: int = 0


class DiagnosticLogger:
    """Two-tier diagnostic logger with automatic change detection."""

    _instance: Optional['DiagnosticLogger'] = None

    def __init__(self, entity_manager, time_manager,
                 summary_path="logs/villager_summary.txt",
                 detail_path="logs/villager_detail.txt"):
        self.em = entity_manager
        self.tm = time_manager
        self._summary_path = summary_path
        self._detail_path = detail_path
        self._summary_file = None
        self._detail_file = None
        self._prev_states: Dict[int, VillagerStateCache] = {}
        self._villager_ids = []
        self._day_stats = DayStats()
        self._last_snapshot_hour = -1
        self._last_summary_snapshot_hour = -1
        self._last_day = -1
        self._enabled = False
        # Deduplication: track last logged message per villager to suppress repeats
        self._last_event_msg: Dict[int, str] = {}
        # Cooldown: minimum ticks between same-category events per villager
        self._event_cooldowns: Dict[str, int] = {}  # key="vid:category" -> last tick logged

        DiagnosticLogger._instance = self

    @classmethod
    def get_instance(cls) -> Optional['DiagnosticLogger']:
        return cls._instance

    # ─── Lifecycle ───────────────────────────────────────────────

    def start(self, villager_ids: list, config_manager=None):
        """Open files, write headers, initialize caches."""
        self._villager_ids = list(villager_ids)
        self._enabled = True

        # Ensure directory exists
        for path in [self._summary_path, self._detail_path]:
            os.makedirs(os.path.dirname(path), exist_ok=True)

        self._summary_file = open(self._summary_path, "w", encoding="utf-8")
        self._detail_file = open(self._detail_path, "w", encoding="utf-8")

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        season = self.tm.get_season() if hasattr(self.tm, 'get_season') else "unknown"
        num_v = len(self._villager_ids)

        # Summary header
        self._write_summary(f"=== VILLAGE SUMMARY LOG ===")
        self._write_summary(f"Start: {now} | Season: {season} | Villagers: {num_v}")
        self._write_summary("")

        # Detail header
        self._write_detail(f"=== VILLAGE DETAIL LOG ===")
        self._write_detail(f"Start: {now} | Season: {season} | Villagers: {num_v}")
        if config_manager:
            day_len = config_manager.get("simulation.day_length_seconds", "?")
            hunger_rate = config_manager.get("entities.villager.needs.hunger_per_hour", "?")
            tired_rate = config_manager.get("entities.villager.needs.tiredness_per_hour_working", "?")
            self._write_detail(f"Config: day_length={day_len}s, hunger_per_hour={hunger_rate}, tiredness_work={tired_rate}")
        self._write_detail("")

        # Initialize caches
        for vid in self._villager_ids:
            self._prev_states[vid] = self._capture_state(vid)

        self._last_day = self.tm.day
        self._last_snapshot_hour = int(self.tm.time_of_day)
        self._last_summary_snapshot_hour = int(self.tm.time_of_day)

        # Initial snapshot
        self._write_snapshot_detail()
        self._write_snapshot_summary()

    def stop(self):
        """Write day summary, close files."""
        if not self._enabled:
            return
        self._write_day_summary()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._write_summary(f"\n=== LOG END: {now} ===")
        self._write_detail(f"\n=== LOG END: {now} ===")
        if self._summary_file:
            self._summary_file.close()
        if self._detail_file:
            self._detail_file.close()
        self._enabled = False

    # ─── Per-Tick Change Detection ──────────────────────────────

    def detect_changes(self):
        """Call every tick. Compares current state to cached state, logs diffs."""
        if not self._enabled:
            return

        current_hour = int(self.tm.time_of_day)

        # Check for periodic snapshots
        # Detail: every 1 game hour
        if current_hour != self._last_snapshot_hour:
            self._write_snapshot_detail()
            self._last_snapshot_hour = current_hour

        # Summary: every 2 game hours
        if current_hour != self._last_summary_snapshot_hour and current_hour % 2 == 0:
            self._write_snapshot_summary()
            self._last_summary_snapshot_hour = current_hour

        # Check for day change
        if self.tm.day != self._last_day:
            self._write_day_summary()
            self._day_stats = DayStats()
            self._last_day = self.tm.day

        # Per-villager change detection
        for vid in self._villager_ids:
            if not self.em.has_entity(vid):
                continue
            current = self._capture_state(vid)
            prev = self._prev_states.get(vid)
            if prev is None:
                self._prev_states[vid] = current
                continue
            self._diff_and_log(vid, prev, current)
            self._prev_states[vid] = current

    # ─── Explicit Event Logging (called by systems) ─────────────

    _HEX_ONLY = re.compile(r'^[a-fA-F]+$')

    @classmethod
    def _normalize_key(cls, message: str) -> str:
        """Strip numbers, UUIDs, and hex-like IDs to create a stable dedup key.
        Keeps only words with 3+ alpha chars that contain at least one non-hex letter.
        e.g. 'AI: Urgent hunger=50.6, interrupting sleep' -> 'Urgent hunger interrupting sleep'
        e.g. 'AI: Assigned job #73773565-c641: chop at (15,5)' -> 'Assigned chop'
        """
        words = re.sub(r'[^a-zA-Z ]+', ' ', message).split()
        return ' '.join(
            w for w in words
            if len(w) >= 3 and not cls._HEX_ONLY.match(w)
        )

    def log(self, level: DiagLevel, villager_id: int, message: str):
        """Log an event at the specified level. Deduplicates repeated messages per villager."""
        if not self._enabled:
            return

        # Deduplication: normalize the message (strip numbers) to create a stable key
        norm_key = f"{villager_id}:{self._normalize_key(message)}"
        current_tick = self.tm.total_ticks
        last_tick = self._event_cooldowns.get(norm_key, -9999)

        # Only allow same type of message once per 300 ticks (~5 seconds / ~1 game-minute)
        if current_tick - last_tick < 300:
            return
        self._event_cooldowns[norm_key] = current_tick

        prefix = self._time_prefix(villager_id)
        line = f"{prefix} {message}"
        if level == DiagLevel.SUMMARY:
            self._write_summary(line)
            self._write_detail(line)
        else:
            self._write_detail(line)

    def log_summary(self, villager_id: int, message: str):
        """Shorthand for SUMMARY level log."""
        self.log(DiagLevel.SUMMARY, villager_id, message)

    def log_detail(self, villager_id: int, message: str):
        """Shorthand for DETAIL level log."""
        self.log(DiagLevel.DETAIL, villager_id, message)

    # ─── Day Stats Tracking ─────────────────────────────────────

    def record_food_consumed(self):
        self._day_stats.food_consumed += 1

    def record_job_completed(self):
        self._day_stats.jobs_completed += 1

    def record_tree_chopped(self):
        self._day_stats.trees_chopped += 1

    def record_crop_harvested(self):
        self._day_stats.crops_harvested += 1

    def record_fish_caught(self):
        self._day_stats.fish_caught += 1

    def record_trap_caught(self):
        self._day_stats.traps_caught += 1

    def record_resource_gathered(self, item_type: str, amount: int):
        self._day_stats.resources_gathered[item_type] = (
            self._day_stats.resources_gathered.get(item_type, 0) + amount
        )

    # ─── Internal: State Capture ────────────────────────────────

    def _capture_state(self, vid: int) -> VillagerStateCache:
        """Capture current villager state for change detection."""
        from src.components.data_components import (
            ActionComponent, InventoryComponent, HungerComponent,
            TirednessComponent, MoodComponent, ColdComponent,
            SleepStateComponent, RoutineComponent, JobComponent
        )

        cache = VillagerStateCache()

        action = self.em.get_component(vid, ActionComponent)
        if action:
            cache.action = action.current_action or "idle"

        routine = self.em.get_component(vid, RoutineComponent)
        if routine:
            cache.routine_state = routine.current_state or ""

        job = self.em.get_component(vid, JobComponent)
        if job:
            cache.job_type = job.job_type
            cache.job_id = job.job_id
        else:
            cache.job_type = None
            cache.job_id = None

        sleep = self.em.get_component(vid, SleepStateComponent)
        if sleep:
            cache.is_sleeping = sleep.is_sleeping

        inv = self.em.get_component(vid, InventoryComponent)
        if inv:
            cache.inventory_snapshot = dict(inv.items)

        hunger = self.em.get_component(vid, HungerComponent)
        if hunger:
            cache.hunger_bracket = self._hunger_bracket(hunger.hunger)

        tired = self.em.get_component(vid, TirednessComponent)
        if tired:
            cache.tiredness_bracket = self._tiredness_bracket(tired.tiredness)

        mood = self.em.get_component(vid, MoodComponent)
        if mood:
            cache.mood_bracket = self._mood_bracket(mood.mood)

        cold = self.em.get_component(vid, ColdComponent)
        if cold:
            cache.cold_bracket = self._cold_bracket(cold.cold)

        return cache

    # ─── Internal: Diff and Log ─────────────────────────────────

    def _can_log_change(self, vid: int, category: str, cooldown_ticks: int = 60) -> bool:
        """Check if a change-detected event should be logged (cooldown-based)."""
        key = f"cd:{vid}:{category}"
        current_tick = self.tm.total_ticks
        last_tick = self._event_cooldowns.get(key, -9999)
        if current_tick - last_tick < cooldown_ticks:
            return False
        self._event_cooldowns[key] = current_tick
        return True

    def _diff_and_log(self, vid: int, prev: VillagerStateCache, curr: VillagerStateCache):
        """Compare two states and log meaningful changes."""
        from src.components.data_components import (
            HungerComponent, TirednessComponent, MoodComponent, ColdComponent
        )

        prefix = self._time_prefix(vid)

        # --- Action changed ---
        if curr.action != prev.action:
            # Skip noisy oscillations: idle<->move is very common and not useful
            is_move_oscillation = (
                (prev.action == "idle" and curr.action == "move") or
                (prev.action == "move" and curr.action == "idle")
            )
            # Summary: only log meaningful action changes (not idle<->move)
            if not is_move_oscillation:
                self._write_summary(f"{prefix} Action: {prev.action} -> {curr.action}")
                self._write_detail(f"{prefix} Action: {prev.action} -> {curr.action}")
            # Detail: log move oscillations at reduced rate
            elif self._can_log_change(vid, "action_move", 300):
                self._write_detail(f"{prefix} Action: {prev.action} -> {curr.action}")

        # --- Routine changed ---
        if curr.routine_state != prev.routine_state:
            self._write_summary(f"{prefix} Routine: {prev.routine_state} -> {curr.routine_state}")
            self._write_detail(f"{prefix} Routine: {prev.routine_state} -> {curr.routine_state}")

        # --- Job changed ---
        if curr.job_type != prev.job_type or curr.job_id != prev.job_id:
            if curr.job_type and curr.job_type != prev.job_type:
                # Job type changed - log to summary with cooldown to avoid chop/haul oscillation
                if self._can_log_change(vid, "job_type_change", 300):
                    self._write_summary(f"{prefix} Job: {curr.job_type}")
                if self._can_log_change(vid, f"job_assign_{curr.job_type}", 120):
                    self._write_detail(f"{prefix} Job assigned: {curr.job_type} (id: {curr.job_id})")
            elif curr.job_type and curr.job_id != prev.job_id:
                # Same job type but different job - only log to detail with cooldown
                if self._can_log_change(vid, f"job_reassign_{curr.job_type}", 300):
                    self._write_detail(f"{prefix} Job re-assigned: {curr.job_type}")
            elif not curr.job_type and prev.job_type:
                # Job cleared (could be completed or released back to pool)
                if self._can_log_change(vid, "job_complete", 300):
                    self._write_detail(f"{prefix} Job ended: {prev.job_type}")

        # --- Sleep state changed ---
        if curr.is_sleeping != prev.is_sleeping:
            state_str = "fell asleep" if curr.is_sleeping else "woke up"
            self._write_summary(f"{prefix} {state_str}")
            self._write_detail(f"{prefix} {state_str}")

        # --- Hunger threshold ---
        if curr.hunger_bracket != prev.hunger_bracket:
            hunger = self.em.get_component(vid, HungerComponent)
            val = hunger.hunger if hunger else 0
            label = self._hunger_label(curr.hunger_bracket)
            is_critical = curr.hunger_bracket >= 2  # >= 50
            if is_critical:
                self._write_summary(f"{prefix} !! HUNGER {label}: {val:.1f}")
                self._day_stats.hunger_warnings += 1
            self._write_detail(f"{prefix} Hunger crossed threshold -> {label} ({val:.1f})")

        # --- Tiredness threshold ---
        if curr.tiredness_bracket != prev.tiredness_bracket:
            tired = self.em.get_component(vid, TirednessComponent)
            val = tired.tiredness if tired else 0
            label = self._tiredness_label(curr.tiredness_bracket)
            is_critical = curr.tiredness_bracket >= 2  # >= 90
            if is_critical:
                self._write_summary(f"{prefix} !! TIREDNESS {label}: {val:.1f}")
                self._day_stats.tiredness_warnings += 1
            self._write_detail(f"{prefix} Tiredness crossed threshold -> {label} ({val:.1f})")

        # --- Mood threshold ---
        if curr.mood_bracket != prev.mood_bracket:
            mood = self.em.get_component(vid, MoodComponent)
            val = mood.mood if mood else 0
            label = self._mood_label(curr.mood_bracket)
            is_critical = curr.mood_bracket <= 0  # <= 30
            if is_critical:
                self._write_summary(f"{prefix} !! MOOD LOW: {val:.1f}")
                self._day_stats.mood_warnings += 1
            self._write_detail(f"{prefix} Mood crossed threshold -> {label} ({val:.1f})")

        # --- Cold threshold ---
        if curr.cold_bracket != prev.cold_bracket:
            cold = self.em.get_component(vid, ColdComponent)
            val = cold.cold if cold else 0
            label = self._cold_label(curr.cold_bracket)
            is_critical = curr.cold_bracket >= 2  # >= 60
            if is_critical:
                self._write_summary(f"{prefix} !! COLD {label}: {val:.1f}")
            self._write_detail(f"{prefix} Cold crossed threshold -> {label} ({val:.1f})")

        # --- Inventory changed (detail only, with cooldown) ---
        if curr.inventory_snapshot != prev.inventory_snapshot:
            if self._can_log_change(vid, "inventory", 30):
                deltas = self._inventory_delta(prev.inventory_snapshot, curr.inventory_snapshot)
                if deltas:
                    delta_str = ", ".join(deltas)
                    self._write_detail(f"{prefix} Inventory: {delta_str} (now: {curr.inventory_snapshot})")

    # ─── Internal: Snapshots ────────────────────────────────────

    def _write_snapshot_summary(self):
        """Write compact one-line-per-villager snapshot to summary."""
        from src.components.data_components import (
            HungerComponent, TirednessComponent, MoodComponent, ColdComponent,
            ActionComponent, RoutineComponent
        )

        game_time = self._game_time_str()
        self._write_summary(f"\n{'─' * 4} {game_time} SNAPSHOT {'─' * 4}")

        for vid in self._villager_ids:
            if not self.em.has_entity(vid):
                continue
            hunger = self.em.get_component(vid, HungerComponent)
            tired = self.em.get_component(vid, TirednessComponent)
            mood = self.em.get_component(vid, MoodComponent)
            cold = self.em.get_component(vid, ColdComponent)
            action = self.em.get_component(vid, ActionComponent)
            routine = self.em.get_component(vid, RoutineComponent)

            h = f"{hunger.hunger:.0f}" if hunger else "?"
            t = f"{tired.tiredness:.0f}" if tired else "?"
            m = f"{mood.mood:.0f}" if mood else "?"
            c = f"{cold.cold:.0f}" if cold else "?"
            act = action.current_action if action else "?"
            rt = routine.current_state if routine else "?"

            idx = self._villager_ids.index(vid)
            self._write_summary(f"V{idx} | Hunger:{h:>3} Tired:{t:>3} Mood:{m:>3} Cold:{c:>3} | {act:<10} | Routine:{rt}")

        self._write_summary("")

    def _write_snapshot_detail(self):
        """Write multi-line detailed snapshot to detail file."""
        from src.components.data_components import (
            PositionComponent, HungerComponent, TirednessComponent, MoodComponent,
            ColdComponent, ActionComponent, RoutineComponent, JobComponent,
            SleepStateComponent, InventoryComponent
        )
        from src.components.skill_component import SkillComponent

        game_time = self._game_time_str()
        tick = self.tm.total_ticks
        self._write_detail(f"\n{'═' * 4} {game_time} (Tick {tick}) SNAPSHOT {'═' * 4}")

        for vid in self._villager_ids:
            if not self.em.has_entity(vid):
                continue
            pos = self.em.get_component(vid, PositionComponent)
            hunger = self.em.get_component(vid, HungerComponent)
            tired = self.em.get_component(vid, TirednessComponent)
            mood = self.em.get_component(vid, MoodComponent)
            cold = self.em.get_component(vid, ColdComponent)
            action = self.em.get_component(vid, ActionComponent)
            routine = self.em.get_component(vid, RoutineComponent)
            job = self.em.get_component(vid, JobComponent)
            sleep = self.em.get_component(vid, SleepStateComponent)
            inv = self.em.get_component(vid, InventoryComponent)
            skill = self.em.get_component(vid, SkillComponent)

            idx = self._villager_ids.index(vid)

            pos_str = f"Pos:({pos.x},{pos.y})" if pos else "Pos:?"
            h = f"{hunger.hunger:.2f}" if hunger else "?"
            t = f"{tired.tiredness:.2f}" if tired else "?"
            m = f"{mood.mood:.2f}" if mood else "?"
            c = f"{cold.cold:.2f}" if cold else "?"

            act_str = action.current_action if action else "?"
            job_str = f"{job.job_type}(id:{job.job_id})" if job else "None"
            rt_str = routine.current_state if routine else "?"
            sleep_str = "Yes" if (sleep and sleep.is_sleeping) else "No"

            self._write_detail(f"[V{idx}] {pos_str} | Hunger:{h} Tired:{t} Mood:{m} Cold:{c}")
            self._write_detail(f"     Action:{act_str} | Job:{job_str} | Routine:{rt_str} | Sleep:{sleep_str}")

            inv_str = dict(inv.items) if inv and inv.items else "{}"
            self._write_detail(f"     Inv: {inv_str}")

            if skill and skill.skills:
                sk_str = ", ".join([f"{k}:{v:.2f}" for k, v in skill.skills.items()])
                self._write_detail(f"     Skills: {sk_str}")

        self._write_detail("")

    def _write_day_summary(self):
        """Write end-of-day summary to summary file."""
        s = self._day_stats
        day_num = self._last_day

        self._write_summary(f"\n{'═' * 4} DAY {day_num} SUMMARY {'═' * 4}")
        self._write_summary(f"Food consumed: {s.food_consumed} | Jobs completed: {s.jobs_completed} | Trees chopped: {s.trees_chopped}")
        self._write_summary(f"Crops harvested: {s.crops_harvested} | Fish caught: {s.fish_caught} | Traps caught: {s.traps_caught}")
        if s.resources_gathered:
            self._write_summary(f"Resources gathered: {s.resources_gathered}")
        alerts = []
        if s.hunger_warnings:
            alerts.append(f"{s.hunger_warnings} hunger")
        if s.tiredness_warnings:
            alerts.append(f"{s.tiredness_warnings} tiredness")
        if s.mood_warnings:
            alerts.append(f"{s.mood_warnings} mood")
        if s.cold_damage_events:
            alerts.append(f"{s.cold_damage_events} cold damage")
        alert_str = ", ".join(alerts) if alerts else "none"
        self._write_summary(f"Alerts: {alert_str}")
        self._write_summary("")

    # ─── Internal: Bracket Helpers ──────────────────────────────

    @staticmethod
    def _hunger_bracket(val: float) -> int:
        if val < 30: return 0
        if val < 50: return 1
        if val < 80: return 2
        return 3

    @staticmethod
    def _tiredness_bracket(val: float) -> int:
        if val < 50: return 0
        if val < 90: return 1
        return 2

    @staticmethod
    def _mood_bracket(val: float) -> int:
        if val < 30: return 0
        if val < 70: return 1
        return 2

    @staticmethod
    def _cold_bracket(val: float) -> int:
        if val < 30: return 0
        if val < 60: return 1
        return 2

    @staticmethod
    def _hunger_label(bracket: int) -> str:
        return ["low(<30)", "moderate(30-50)", "HIGH(50-80)", "CRITICAL(>80)"][bracket]

    @staticmethod
    def _tiredness_label(bracket: int) -> str:
        return ["low(<50)", "moderate(50-90)", "CRITICAL(>90)"][bracket]

    @staticmethod
    def _mood_label(bracket: int) -> str:
        return ["LOW(<30)", "fair(30-70)", "good(>70)"][bracket]

    @staticmethod
    def _cold_label(bracket: int) -> str:
        return ["low(<30)", "moderate(30-60)", "HIGH(>60)"][bracket]

    # ─── Internal: Formatting ───────────────────────────────────

    def _time_prefix(self, vid: int) -> str:
        """Format: [D1 08:30] V0 |"""
        day = self.tm.day
        hour = int(self.tm.time_of_day)
        minute = int((self.tm.time_of_day % 1.0) * 60)
        idx = self._villager_ids.index(vid) if vid in self._villager_ids else vid
        return f"[D{day} {hour:02d}:{minute:02d}] V{idx} |"

    def _game_time_str(self) -> str:
        day = self.tm.day
        hour = int(self.tm.time_of_day)
        minute = int((self.tm.time_of_day % 1.0) * 60)
        season = self.tm.get_season() if hasattr(self.tm, 'get_season') else ""
        return f"Day {day}, {hour:02d}:{minute:02d} ({season})"

    @staticmethod
    def _inventory_delta(prev: Dict[str, int], curr: Dict[str, int]) -> list:
        """Calculate inventory deltas like +2 log, -1 food_wheat."""
        deltas = []
        all_keys = set(list(prev.keys()) + list(curr.keys()))
        for key in sorted(all_keys):
            old_val = prev.get(key, 0)
            new_val = curr.get(key, 0)
            diff = new_val - old_val
            if diff > 0:
                deltas.append(f"+{diff} {key}")
            elif diff < 0:
                deltas.append(f"{diff} {key}")
        return deltas

    # ─── Internal: File Writing ─────────────────────────────────

    def _write_summary(self, line: str):
        if self._summary_file:
            self._summary_file.write(line + "\n")
            self._summary_file.flush()

    def _write_detail(self, line: str):
        if self._detail_file:
            self._detail_file.write(line + "\n")
            self._detail_file.flush()
