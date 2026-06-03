"""Tests for Phase 2 Group 2: Mid-session Adaptive Scheduling."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from backend.routines.adaptive_scheduler import (
    RESCHEDULE_DRIFT_THRESHOLD,
    rebuild_remaining_plan,
    should_reschedule,
)
from backend.live_agent.session_manager import SessionManager, SessionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _block(name: str, mode: str, duration_sec: int) -> dict:
    return {"name": name, "mode": mode, "duration_sec": duration_sec, "items": [], "voice_script": ""}


def _plan(*blocks) -> dict:
    total = sum(b["duration_sec"] for b in blocks)
    return {"blocks": list(blocks), "total_duration_sec": total, "duration_minutes": round(total / 60)}


def _ts_ago(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _make_state(**kwargs) -> SessionState:
    return SessionState(session_id="test-session", **kwargs)


def _make_manager() -> SessionManager:
    with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
        return SessionManager()


# ---------------------------------------------------------------------------
# should_reschedule
# ---------------------------------------------------------------------------

class TestShouldReschedule:
    def test_returns_false_when_no_time_remaining(self):
        plan = _plan(_block("Main", "main", 600))
        assert should_reschedule(routine_plan=plan, time_remaining_sec=None) is False

    def test_returns_false_when_no_plan(self):
        assert should_reschedule(routine_plan=None, time_remaining_sec=300) is False

    def test_returns_false_when_plan_has_no_blocks(self):
        assert should_reschedule(routine_plan={"blocks": []}, time_remaining_sec=300) is False

    def test_returns_false_within_threshold(self):
        # Plan = 600s, remaining = 550s → drift = 50/600 ≈ 8% — within 20%
        plan = _plan(_block("Main", "main", 600))
        assert should_reschedule(routine_plan=plan, time_remaining_sec=550) is False

    def test_returns_true_beyond_threshold(self):
        # Plan = 600s, remaining = 300s → drift = 300/600 = 50% — beyond 20%
        plan = _plan(_block("Main", "main", 600))
        assert should_reschedule(routine_plan=plan, time_remaining_sec=300) is True

    def test_boundary_exactly_at_threshold_is_not_rescheduled(self):
        # drift == RESCHEDULE_DRIFT_THRESHOLD exactly → False (strictly greater than)
        plan = _plan(_block("Main", "main", 100))
        under = int(100 * (1 - RESCHEDULE_DRIFT_THRESHOLD))
        assert should_reschedule(routine_plan=plan, time_remaining_sec=under) is False

    def test_returns_true_for_overrun(self):
        # Plan = 600s, remaining = 900s → session running over
        plan = _plan(_block("Main", "main", 600))
        assert should_reschedule(routine_plan=plan, time_remaining_sec=900) is True

    def test_real_scenario_two_interruptions(self):
        # 10-min session, 8 min of blocks remain, but only 3 min of actual time left
        plan = _plan(
            _block("Warmup", "warmup", 120),
            _block("Main", "main", 360),
            _block("Cooldown", "cooldown", 120),
        )
        assert should_reschedule(routine_plan=plan, time_remaining_sec=180) is True

    def test_skips_completed_blocks_when_index_set(self):
        # Warmup (120s) is done; only Main (360s) + Cooldown (120s) = 480s remain in plan
        # time_remaining = 180s → drift = 300/480 = 62.5% → reschedule
        plan = _plan(
            _block("Warmup", "warmup", 120),
            _block("Main", "main", 360),
            _block("Cooldown", "cooldown", 120),
        )
        assert should_reschedule(routine_plan=plan, time_remaining_sec=180, current_block_index=1) is True

    def test_no_reschedule_when_only_cooldown_remains(self):
        # Only cooldown (60s) left in plan; 60s remaining → no drift
        plan = _plan(
            _block("Main", "main", 300),
            _block("Cooldown", "cooldown", 60),
        )
        assert should_reschedule(routine_plan=plan, time_remaining_sec=60, current_block_index=1) is False


# ---------------------------------------------------------------------------
# rebuild_remaining_plan
# ---------------------------------------------------------------------------

class TestRebuildRemainingPlan:
    def test_output_fits_within_remaining_plus_tolerance(self):
        plan = _plan(
            _block("Warmup", "warmup", 120),
            _block("Main 1", "main", 240),
            _block("Main 2", "main", 180),
            _block("Cooldown", "cooldown", 60),
        )
        result = rebuild_remaining_plan(plan, remaining_sec=300)
        total = sum(b["duration_sec"] for b in result["blocks"])
        assert total <= 300 + 30

    def test_cooldown_always_last(self):
        plan = _plan(
            _block("Main", "main", 300),
            _block("Cooldown", "cooldown", 60),
        )
        result = rebuild_remaining_plan(plan, remaining_sec=120)
        assert result["blocks"][-1]["mode"] == "cooldown"

    def test_cooldown_preserved_when_only_cooldown_fits(self):
        plan = _plan(
            _block("Main", "main", 600),
            _block("Cooldown", "cooldown", 60),
        )
        result = rebuild_remaining_plan(plan, remaining_sec=60)
        modes = [b["mode"] for b in result["blocks"]]
        assert modes == ["cooldown"]

    def test_trims_longest_main_blocks_first(self):
        plan = _plan(
            _block("Short", "main", 60),
            _block("Long", "main", 300),
            _block("Cooldown", "cooldown", 60),
        )
        # remaining = 150s → cooldown=60, budget=90 → drop Long (300), keep Short (60)
        result = rebuild_remaining_plan(plan, remaining_sec=150)
        names = [b["name"] for b in result["blocks"]]
        assert "Short" in names
        assert "Long" not in names

    def test_total_duration_sec_updated(self):
        plan = _plan(
            _block("Main", "main", 600),
            _block("Cooldown", "cooldown", 60),
        )
        result = rebuild_remaining_plan(plan, remaining_sec=120)
        expected_total = sum(b["duration_sec"] for b in result["blocks"])
        assert result["total_duration_sec"] == expected_total

    def test_other_plan_keys_preserved(self):
        plan = {**_plan(_block("Main", "main", 300)), "mode": "timeboxed", "library_version": "1.0"}
        result = rebuild_remaining_plan(plan, remaining_sec=300)
        assert result["mode"] == "timeboxed"
        assert result["library_version"] == "1.0"

    def test_no_blocks_returns_empty(self):
        plan = {"blocks": [], "total_duration_sec": 0}
        result = rebuild_remaining_plan(plan, remaining_sec=300)
        assert result["blocks"] == []

    def test_skips_completed_blocks_via_index(self):
        # Warmup (120s) is done; rebuild should only consider Main + Cooldown
        plan = _plan(
            _block("Warmup", "warmup", 120),
            _block("Main", "main", 300),
            _block("Cooldown", "cooldown", 60),
        )
        result = rebuild_remaining_plan(plan, remaining_sec=400, current_block_index=1)
        names = [b["name"] for b in result["blocks"]]
        assert "Warmup" not in names
        assert "Main" in names
        assert "Cooldown" in names

    def test_current_block_index_zero_is_same_as_default(self):
        plan = _plan(_block("Main", "main", 300), _block("Cooldown", "cooldown", 60))
        r1 = rebuild_remaining_plan(plan, remaining_sec=200)
        r2 = rebuild_remaining_plan(plan, remaining_sec=200, current_block_index=0)
        assert r1 == r2


# ---------------------------------------------------------------------------
# maybe_reschedule (integration through SessionManager)
# ---------------------------------------------------------------------------

class TestMaybeReschedule:
    def _make_state_with_plan(self, planned_minutes: int, elapsed_sec: float, plan: dict) -> SessionState:
        state = _make_state(
            planned_duration_minutes=planned_minutes,
            routine_plan=plan,
            total_pause_time_seconds=0.0,
        )
        state.started_at = _ts_ago(elapsed_sec)
        return state

    def test_returns_false_when_no_reschedule_needed(self):
        mgr = _make_manager()
        plan = _plan(_block("Main", "main", 540), _block("Cooldown", "cooldown", 60))
        state = self._make_state_with_plan(planned_minutes=10, elapsed_sec=30, plan=plan)
        mgr._mem["test-session"] = state

        result = mgr.maybe_reschedule("test-session", trigger="resume")

        assert result is False
        assert state.routine_plan is plan  # unchanged

    def test_returns_true_and_replaces_plan_when_drift_exceeded(self):
        mgr = _make_manager()
        # 10-min session, 8 min of blocks, but 7 min elapsed → only ~3 min remain
        plan = _plan(
            _block("Main 1", "main", 300),
            _block("Main 2", "main", 180),
            _block("Cooldown", "cooldown", 120),
        )
        state = self._make_state_with_plan(planned_minutes=10, elapsed_sec=420, plan=plan)
        mgr._mem["test-session"] = state

        result = mgr.maybe_reschedule("test-session", trigger="resume")

        assert result is True
        assert state.routine_plan is not plan
        new_total = sum(b["duration_sec"] for b in state.routine_plan["blocks"])
        old_total = 300 + 180 + 120
        assert new_total < old_total

    def test_new_plan_still_has_cooldown(self):
        mgr = _make_manager()
        plan = _plan(
            _block("Main 1", "main", 300),
            _block("Main 2", "main", 300),
            _block("Cooldown", "cooldown", 60),
        )
        state = self._make_state_with_plan(planned_minutes=10, elapsed_sec=480, plan=plan)
        mgr._mem["test-session"] = state

        mgr.maybe_reschedule("test-session", trigger="resume")

        blocks = state.routine_plan["blocks"]
        assert blocks[-1]["mode"] == "cooldown"

    def test_returns_false_when_remaining_time_unknown(self):
        mgr = _make_manager()
        # no planned_duration_minutes → remaining_time_sec() returns None
        plan = _plan(_block("Main", "main", 600))
        state = _make_state(routine_plan=plan)
        mgr._mem["test-session"] = state

        result = mgr.maybe_reschedule("test-session", trigger="resume")

        assert result is False

    def test_resets_current_block_index_after_reschedule(self):
        mgr = _make_manager()
        plan = _plan(
            _block("Warmup", "warmup", 120),
            _block("Main", "main", 600),
            _block("Cooldown", "cooldown", 60),
        )
        state = self._make_state_with_plan(planned_minutes=10, elapsed_sec=420, plan=plan)
        state.current_block_index = 1  # warmup already done
        mgr._mem["test-session"] = state

        mgr.maybe_reschedule("test-session", trigger="resume")

        assert state.current_block_index == 0  # reset after rebuild

    def test_excludes_completed_blocks_from_drift_calculation(self):
        mgr = _make_manager()
        # Warmup (120s) + Main (540s) + Cooldown (60s) = 720s plan
        # Warmup is done (index=1); unstarted = Main + Cooldown = 600s
        # 7 min elapsed → ~3 min left → drift = (600-180)/600 = 70% → reschedule
        plan = _plan(
            _block("Warmup", "warmup", 120),
            _block("Main", "main", 540),
            _block("Cooldown", "cooldown", 60),
        )
        state = self._make_state_with_plan(planned_minutes=10, elapsed_sec=420, plan=plan)
        state.current_block_index = 1
        mgr._mem["test-session"] = state

        result = mgr.maybe_reschedule("test-session", trigger="resume")
        assert result is True
        names = [b["name"] for b in state.routine_plan["blocks"]]
        assert "Warmup" not in names

    def test_advance_block_increments_index(self):
        mgr = _make_manager()
        state = _make_state()
        mgr._mem["test-session"] = state
        assert state.current_block_index == 0

        mgr.advance_block("test-session")
        assert state.current_block_index == 1

        mgr.advance_block("test-session")
        assert state.current_block_index == 2
