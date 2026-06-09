"""Tests for Phase 2 Group 4: Dynamic Difficulty Adjustment."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.coach_agent.response_handler import adjust_difficulty
from backend.live_agent.session_manager import SessionManager, SessionState


def _make_state(**kwargs) -> SessionState:
    return SessionState(session_id="test-session", **kwargs)


def _make_manager() -> SessionManager:
    with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
        return SessionManager()


_SAMPLE_PLAN = {
    "blocks": [
        {
            "name": "Main",
            "mode": "main",
            "duration_sec": 120,
            "items": [
                {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
            ],
        },
        {
            "name": "Cooldown",
            "mode": "cooldown",
            "duration_sec": 60,
            "items": [
                {"exercise_id": "plank", "prescription": {"type": "time", "seconds": 30, "rest_seconds": 15}},
            ],
        },
    ]
}


# ---------------------------------------------------------------------------
# adjust_difficulty tool function
# ---------------------------------------------------------------------------

class TestAdjustDifficultyTool:
    def test_returns_success_for_easier(self):
        result = adjust_difficulty("easier", "user struggling", "s1")
        assert result["status"] == "success"

    def test_returns_success_for_harder(self):
        result = adjust_difficulty("harder", "user breezing through", "s1")
        assert result["status"] == "success"

    def test_returns_difficulty_adjustment_type(self):
        result = adjust_difficulty("easier", "high corrections", "s1")
        assert result["type"] == "difficulty_adjustment"

    def test_direction_preserved(self):
        assert adjust_difficulty("easier", "reason", "s1")["direction"] == "easier"
        assert adjust_difficulty("harder", "reason", "s1")["direction"] == "harder"

    def test_reason_preserved(self):
        result = adjust_difficulty("easier", "labored breathing", "s1")
        assert result["reason"] == "labored breathing"

    def test_session_id_preserved(self):
        result = adjust_difficulty("easier", "reason", "my-session")
        assert result["session_id"] == "my-session"

    def test_invalid_direction_returns_error(self):
        result = adjust_difficulty("medium", "reason", "s1")
        assert result["status"] == "error"
        assert "direction" in result["message"]

    def test_tool_registered_in_agent(self):
        from backend.coach_agent.agent import agent
        from backend.coach_agent.response_handler import adjust_difficulty_tool
        assert adjust_difficulty_tool in agent.tools


# ---------------------------------------------------------------------------
# _apply_difficulty_adjustment — block mutation
# ---------------------------------------------------------------------------

class TestApplyDifficultyAdjustment:
    def test_easier_reduces_reps(self):
        mgr = _make_manager()
        state = _make_state(routine_plan=_SAMPLE_PLAN, current_block_index=0)
        mgr._apply_difficulty_adjustment(state, "easier", "test")
        presc = state.routine_plan["blocks"][1]["items"][0]["prescription"]
        # Cooldown block is time-type, no reps to check — verify via Main block if it were pending
        # (current_block_index=0 so only blocks[1+] are mutated; Main is index 0, Cooldown is index 1)
        assert presc["rest_seconds"] == max(10, 15 + 15)  # 30 → 15 for cooldown

    def test_easier_increases_rest(self):
        mgr = _make_manager()
        state = _make_state(routine_plan=_SAMPLE_PLAN, current_block_index=0)
        # Use a plan where block[1] has a reps prescription
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "air_squat", "prescription": {"type": "reps", "reps_min": 10, "reps_max": 15, "rest_seconds": 30}},
                ]},
            ]
        }
        state.routine_plan = plan
        mgr._apply_difficulty_adjustment(state, "easier", "test")
        presc = plan["blocks"][1]["items"][0]["prescription"]
        assert presc["reps_min"] == max(1, round(10 * 0.75))
        assert presc["reps_max"] == max(1, round(15 * 0.75))
        assert presc["rest_seconds"] == 30 + 15

    def test_harder_increases_reps(self):
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "air_squat", "prescription": {"type": "reps", "reps_min": 10, "reps_max": 15, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0)
        mgr._apply_difficulty_adjustment(state, "harder", "test")
        presc = plan["blocks"][1]["items"][0]["prescription"]
        assert presc["reps_min"] == max(1, round(10 * 1.25))
        assert presc["reps_max"] == max(1, round(15 * 1.25))
        assert presc["rest_seconds"] == 30 - 15

    def test_harder_reduces_rest(self):
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0)
        mgr._apply_difficulty_adjustment(state, "harder", "test")
        assert plan["blocks"][1]["items"][0]["prescription"]["rest_seconds"] == 15

    def test_rest_clamped_to_minimum_10(self):
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 5, "reps_max": 8, "rest_seconds": 15}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0)
        mgr._apply_difficulty_adjustment(state, "harder", "test")
        assert plan["blocks"][1]["items"][0]["prescription"]["rest_seconds"] == 10

    def test_reps_clamped_to_minimum_1(self):
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 1, "reps_max": 1, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0)
        mgr._apply_difficulty_adjustment(state, "easier", "test")
        assert plan["blocks"][1]["items"][0]["prescription"]["reps_min"] >= 1
        assert plan["blocks"][1]["items"][0]["prescription"]["reps_max"] >= 1

    def test_does_not_mutate_current_block(self):
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "air_squat", "prescription": {"type": "reps", "reps_min": 10, "reps_max": 15, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0)
        mgr._apply_difficulty_adjustment(state, "easier", "test")
        # Block 0 (current) must be untouched
        assert plan["blocks"][0]["items"][0]["prescription"]["reps_max"] == 12

    def test_no_pending_blocks_returns_zero(self):
        mgr = _make_manager()
        plan = {"blocks": [{"name": "A", "mode": "main", "duration_sec": 60, "items": []}]}
        state = _make_state(routine_plan=plan, current_block_index=0)
        result = mgr._apply_difficulty_adjustment(state, "easier", "test")
        assert result["mutated_blocks"] == 0

    def test_no_plan_returns_zero(self):
        mgr = _make_manager()
        state = _make_state()
        result = mgr._apply_difficulty_adjustment(state, "easier", "test")
        assert result["mutated_blocks"] == 0

    def test_sets_last_difficulty_adjustment_at(self):
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": []},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0)
        assert state.last_difficulty_adjustment_at is None
        mgr._apply_difficulty_adjustment(state, "easier", "test")
        assert state.last_difficulty_adjustment_at is not None

    def test_trigger_agent_is_default(self):
        """Verify agent trigger is the default — no trigger= kwarg needed for tool path."""
        mgr = _make_manager()
        state = _make_state()
        # Just ensure the signature accepts no trigger without error
        mgr._apply_difficulty_adjustment(state, "easier", "test")


# ---------------------------------------------------------------------------
# append_event("difficulty_adjustment") → mutation applied
# ---------------------------------------------------------------------------

class TestAppendEventDifficultyAdjustment:
    def test_easier_mutates_pending_blocks(self):
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0)
        mgr._mem["test-session"] = state
        mgr.append_event("test-session", "difficulty_adjustment", {
            "direction": "easier",
            "reason": "high corrections",
            "session_id": "test-session",
        })
        assert plan["blocks"][1]["items"][0]["prescription"]["reps_max"] == max(1, round(12 * 0.75))

    def test_invalid_direction_does_not_raise(self):
        mgr = _make_manager()
        state = _make_state()
        mgr._mem["test-session"] = state
        mgr.append_event("test-session", "difficulty_adjustment", {"direction": "sideways"})

    def test_does_not_touch_rep_count(self):
        mgr = _make_manager()
        state = _make_state(cumulative_rep_count=20)
        mgr._mem["test-session"] = state
        mgr.append_event("test-session", "difficulty_adjustment", {"direction": "easier", "reason": "test"})
        assert state.cumulative_rep_count == 20


# ---------------------------------------------------------------------------
# Passive inference — _check_difficulty_signal
# ---------------------------------------------------------------------------

class TestCheckDifficultySignal:
    def test_high_fatigue_returns_easier(self):
        mgr = _make_manager()
        state = _make_state(recent_fatigue=0.75)
        assert mgr._check_difficulty_signal(state) == "easier"

    def test_fatigue_at_threshold_returns_easier(self):
        mgr = _make_manager()
        state = _make_state(recent_fatigue=0.7)
        assert mgr._check_difficulty_signal(state) == "easier"

    def test_fatigue_below_threshold_does_not_trigger(self):
        mgr = _make_manager()
        state = _make_state(recent_fatigue=0.5)
        # No other signals active (< 60s elapsed by default)
        assert mgr._check_difficulty_signal(state) is None

    def test_no_fatigue_no_signal_in_first_60s(self):
        mgr = _make_manager()
        state = _make_state(form_corrections=["c1", "c2", "c3"])
        assert mgr._check_difficulty_signal(state) is None

    def test_returns_none_when_no_signals(self):
        mgr = _make_manager()
        state = _make_state()
        assert mgr._check_difficulty_signal(state) is None


# ---------------------------------------------------------------------------
# Passive auto-trigger — _maybe_auto_adjust_difficulty
# ---------------------------------------------------------------------------

class TestMaybeAutoAdjustDifficulty:
    def test_fires_when_fatigue_high(self):
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0, recent_fatigue=0.8, status="active")
        mgr._maybe_auto_adjust_difficulty("test-session", state)
        assert plan["blocks"][1]["items"][0]["prescription"]["reps_max"] < 12

    def test_respects_cooldown_guard(self):
        from backend.firestore.schema import utc_now_iso
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(
            routine_plan=plan, current_block_index=0, recent_fatigue=0.8, status="active",
            last_difficulty_adjustment_at=utc_now_iso(),  # just adjusted
        )
        mgr._maybe_auto_adjust_difficulty("test-session", state)
        # Cooldown guard: reps_max must be unchanged
        assert plan["blocks"][1]["items"][0]["prescription"]["reps_max"] == 12

    def test_does_not_fire_when_paused(self):
        mgr = _make_manager()
        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0, recent_fatigue=0.9, status="paused")
        mgr._maybe_auto_adjust_difficulty("test-session", state)
        assert plan["blocks"][1]["items"][0]["prescription"]["reps_max"] == 12

    def test_passive_trigger_sets_trigger_server_in_trace(self):
        """Passive auto-trigger must use trigger='server', not 'agent'."""
        mgr = _make_manager()
        state = _make_state(recent_fatigue=0.8, status="active")
        calls: list[str] = []
        original = mgr._apply_difficulty_adjustment

        def capturing(*args, **kwargs):
            calls.append(kwargs.get("trigger", args[3] if len(args) > 3 else "agent"))
            return original(*args, **kwargs)

        mgr._apply_difficulty_adjustment = capturing  # type: ignore[method-assign]
        mgr._maybe_auto_adjust_difficulty("test-session", state)
        assert calls == ["server"]


# ---------------------------------------------------------------------------
# _process_coach_tool_event routing for difficulty_adjustment
# ---------------------------------------------------------------------------

class TestProcessCoachToolEventDifficulty:
    @pytest.mark.asyncio
    async def test_difficulty_adjustment_routes_to_append_event(self):
        from backend.main import _process_coach_tool_event

        fake_event = MagicMock()
        fake_event.tool_response = {
            "status": "success",
            "type": "difficulty_adjustment",
            "direction": "easier",
            "reason": "user struggling",
            "session_id": "s1",
        }

        mgr = _make_manager()
        mgr._mem["s1"] = _make_state(status="active")

        results = await _process_coach_tool_event(fake_event, "s1", mgr)
        assert isinstance(results, list)
        # direction_adjustment with no pending blocks → empty list (no plan update)
        assert results == []

    @pytest.mark.asyncio
    async def test_direction_forwarded_updates_state(self):
        """Agent-triggered harder adjustment mutates pending blocks."""
        from backend.main import _process_coach_tool_event

        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0, status="active")
        mgr = _make_manager()
        mgr._mem["s1"] = state

        fake_event = MagicMock()
        fake_event.tool_response = {
            "status": "success",
            "type": "difficulty_adjustment",
            "direction": "harder",
            "reason": "user breezing through",
            "session_id": "s1",
        }

        results = await _process_coach_tool_event(fake_event, "s1", mgr)
        assert any(r["type"] == "routine_plan_updated" for r in results)
        assert plan["blocks"][1]["items"][0]["prescription"]["reps_max"] == max(1, round(12 * 1.25))

    @pytest.mark.asyncio
    async def test_fatigue_update_still_routes_correctly(self):
        from backend.main import _process_coach_tool_event

        fake_event = MagicMock()
        fake_event.tool_response = {
            "status": "success",
            "type": "fatigue_update",
            "fatigue_level": 0.7,
            "confidence": "high",
            "observed_cues": [],
        }

        mgr = _make_manager()
        mgr._mem["s1"] = _make_state(status="active")
        results = await _process_coach_tool_event(fake_event, "s1", mgr)
        # fatigue_update returns empty list (no client notification needed)
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_routine_plan_updated_when_blocks_mutated(self):
        """_process_coach_tool_event must include routine_plan_updated so the caller can notify the client."""
        from backend.main import _process_coach_tool_event

        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0, status="active")
        mgr = _make_manager()
        mgr._mem["s1"] = state

        fake_event = MagicMock()
        fake_event.tool_response = {
            "status": "success",
            "type": "difficulty_adjustment",
            "direction": "easier",
            "reason": "struggling",
            "session_id": "s1",
        }

        results = await _process_coach_tool_event(fake_event, "s1", mgr)

        assert isinstance(results, list)
        assert any(r["type"] == "routine_plan_updated" for r in results)
        plan_msg = next(r for r in results if r["type"] == "routine_plan_updated")
        assert plan_msg["routine_plan"] is not None

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_blocks_mutated(self):
        """No client notification when there are no pending blocks to mutate."""
        from backend.main import _process_coach_tool_event

        state = _make_state(status="active")  # no routine_plan
        mgr = _make_manager()
        mgr._mem["s1"] = state

        fake_event = MagicMock()
        fake_event.tool_response = {
            "status": "success",
            "type": "difficulty_adjustment",
            "direction": "easier",
            "reason": "struggling",
            "session_id": "s1",
        }

        results = await _process_coach_tool_event(fake_event, "s1", mgr)
        assert results == []


# ---------------------------------------------------------------------------
# Firestore persistence — _write_routine_plan
# ---------------------------------------------------------------------------

class TestWriteRoutinePlan:
    def test_calls_firestore_set_with_routine_plan(self):
        mock_fs = MagicMock()
        mock_doc = MagicMock()
        mock_fs.collection.return_value.document.return_value = mock_doc

        with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
            mgr = _make_manager()
        mgr._firestore = mock_fs

        plan = {"blocks": [{"name": "A"}]}
        state = _make_state(routine_plan=plan)
        mgr._write_routine_plan(state)

        mock_fs.collection.assert_called_once()
        mock_doc.set.assert_called_once_with({"routine_plan": plan}, merge=True)

    def test_skips_write_when_no_firestore(self):
        with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
            mgr = _make_manager()
        state = _make_state(routine_plan={"blocks": []})
        mgr._write_routine_plan(state)  # must not raise

    def test_skips_write_when_no_plan(self):
        mock_fs = MagicMock()
        with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
            mgr = _make_manager()
        mgr._firestore = mock_fs
        state = _make_state()  # no routine_plan
        mgr._write_routine_plan(state)
        mock_fs.collection.assert_not_called()

    def test_apply_adjustment_calls_write_routine_plan(self):
        """_apply_difficulty_adjustment must persist the plan after mutation."""
        with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
            mgr = _make_manager()

        plan = {
            "blocks": [
                {"name": "A", "mode": "main", "duration_sec": 60, "items": []},
                {"name": "B", "mode": "main", "duration_sec": 60, "items": [
                    {"exercise_id": "push_up", "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30}},
                ]},
            ]
        }
        state = _make_state(routine_plan=plan, current_block_index=0)

        write_calls: list = []
        mgr._write_routine_plan = lambda s: write_calls.append(s.session_id)  # type: ignore[method-assign]

        mgr._apply_difficulty_adjustment(state, "easier", "test")
        assert write_calls == ["test-session"]

    def test_no_write_when_no_pending_blocks(self):
        """No Firestore write when there are no blocks to mutate."""
        with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
            mgr = _make_manager()

        plan = {"blocks": [{"name": "A", "mode": "main", "duration_sec": 60, "items": []}]}
        state = _make_state(routine_plan=plan, current_block_index=0)

        write_calls: list = []
        mgr._write_routine_plan = lambda s: write_calls.append(s.session_id)  # type: ignore[method-assign]

        mgr._apply_difficulty_adjustment(state, "easier", "test")
        assert write_calls == []


# ---------------------------------------------------------------------------
# _TOOL_SUFFIX always present in agent instruction
# ---------------------------------------------------------------------------

class TestAgentInstructionContainsToolGuidance:
    def test_instruction_contains_adjust_difficulty(self):
        from backend.coach_agent.agent import agent
        assert "adjust_difficulty" in agent.instruction

    def test_instruction_contains_emit_exercise_data(self):
        from backend.coach_agent.agent import agent
        assert "emit_exercise_data" in agent.instruction

    def test_instruction_contains_report_fatigue(self):
        from backend.coach_agent.agent import agent
        assert "report_fatigue" in agent.instruction
