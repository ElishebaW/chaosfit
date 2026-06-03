"""Tests for Group 1: Smarter Interruption Recovery."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.live_agent.session_manager import SessionState, _elapsed_seconds


def _make_state(**kwargs) -> SessionState:
    return SessionState(session_id="test-session", **kwargs)


def _ts_ago(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


class TestElapsedSeconds:
    def test_returns_approximate_elapsed(self):
        ts = _ts_ago(30)
        assert 28 <= _elapsed_seconds(ts) <= 32

    def test_returns_zero_for_future_timestamp(self):
        ts = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
        assert _elapsed_seconds(ts) == 0.0

    def test_returns_zero_for_bad_input(self):
        assert _elapsed_seconds("not-a-timestamp") == 0.0
        assert _elapsed_seconds("") == 0.0


class TestElapsedActiveSec:
    def test_subtracts_pause_time(self):
        state = _make_state(total_pause_time_seconds=30.0)
        state.started_at = _ts_ago(90)
        elapsed = state.elapsed_active_sec()
        assert 55 <= elapsed <= 65  # ~60s active

    def test_zero_for_brand_new_session(self):
        state = _make_state()
        assert state.elapsed_active_sec() >= 0.0

    def test_never_negative(self):
        state = _make_state(total_pause_time_seconds=9999.0)
        assert state.elapsed_active_sec() == 0.0


class TestRemainingTimeSec:
    def test_returns_none_when_no_planned_duration(self):
        state = _make_state()
        assert state.remaining_time_sec() is None

    def test_computes_from_planned_duration(self):
        state = _make_state(planned_duration_minutes=10)
        state.started_at = _ts_ago(180)  # 3 minutes elapsed, 0 pause
        state.total_pause_time_seconds = 0.0
        remaining = state.remaining_time_sec()
        assert remaining is not None
        assert 410 <= remaining <= 430  # ~7 minutes left

    def test_accounts_for_pause_time(self):
        state = _make_state(planned_duration_minutes=10)
        state.started_at = _ts_ago(240)  # 4 min wall-clock
        state.total_pause_time_seconds = 60.0  # 1 min pause → 3 min active
        remaining = state.remaining_time_sec()
        assert remaining is not None
        assert 410 <= remaining <= 430  # ~7 minutes left

    def test_clamps_to_zero_when_overrun(self):
        state = _make_state(planned_duration_minutes=1)
        state.started_at = _ts_ago(180)  # 3 min elapsed, plan was 1 min
        assert state.remaining_time_sec() == 0


class TestContextualResumeSummary:
    def test_all_keys_present(self):
        state = _make_state(
            current_exercise="push_up",
            rep_count=8,
            cumulative_rep_count=23,
            pause_count=1,
            form_corrections=["keep your elbows tucked", "lower your chest"],
        )
        summary = state.contextual_resume_summary()
        assert {"current_exercise", "reps_this_set", "total_reps", "time_remaining_sec",
                "elapsed_active_sec", "pause_count", "last_correction"} <= summary.keys()

    def test_exercise_and_reps(self):
        state = _make_state(current_exercise="push_up", rep_count=8, cumulative_rep_count=23)
        summary = state.contextual_resume_summary()
        assert summary["current_exercise"] == "push_up"
        assert summary["reps_this_set"] == 8
        assert summary["total_reps"] == 23

    def test_last_correction_is_most_recent(self):
        state = _make_state(form_corrections=["first", "second", "third"])
        assert state.contextual_resume_summary()["last_correction"] == "third"

    def test_last_correction_none_when_empty(self):
        state = _make_state()
        assert state.contextual_resume_summary()["last_correction"] is None

    def test_time_remaining_none_when_no_plan(self):
        state = _make_state()
        assert state.contextual_resume_summary()["time_remaining_sec"] is None

    def test_elapsed_active_sec_is_int(self):
        state = _make_state()
        assert isinstance(state.contextual_resume_summary()["elapsed_active_sec"], int)


class TestResumePauseDuration:
    """resume_session() must auto-compute pause duration from paused_at."""

    def _make_manager(self) -> "SessionManager":
        with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
            from backend.live_agent.session_manager import SessionManager
            mgr = SessionManager()
        return mgr

    def test_pause_duration_computed_from_paused_at(self):
        mgr = self._make_manager()
        state = _make_state(pause_count=1)
        state.paused_at = _ts_ago(45)
        state.status = "paused"
        mgr._mem["test-session"] = state

        mgr.resume_session("test-session")

        assert 40 <= state.total_pause_time_seconds <= 50

    def test_pause_duration_zero_when_paused_at_missing(self):
        mgr = self._make_manager()
        state = _make_state()
        state.paused_at = None
        state.status = "paused"
        mgr._mem["test-session"] = state

        mgr.resume_session("test-session")

        assert state.total_pause_time_seconds == 0.0

    def test_explicit_duration_still_accepted(self):
        mgr = self._make_manager()
        state = _make_state()
        state.paused_at = _ts_ago(999)  # would give ~999s if auto-computed
        state.status = "paused"
        mgr._mem["test-session"] = state

        mgr.resume_session("test-session", pause_duration_seconds=10.0)

        assert state.total_pause_time_seconds == 10.0


class TestCompileResumeContext:
    def test_fallback_uses_remaining_when_available(self):
        from backend.main import _compile_resume_context

        context = {
            "current_exercise": "air_squat",
            "reps_this_set": 5,
            "total_reps": 15,
            "time_remaining_sec": 240,
            "elapsed_active_sec": 120,
            "pause_count": 1,
            "last_correction": "push your knees out",
        }

        with patch("backend.main._langfuse") as mock_lf:
            mock_lf.get_prompt.side_effect = Exception("langfuse unavailable")
            result = _compile_resume_context(context)

        assert "air_squat" in result
        assert "5" in result
        assert "remaining" in result  # uses remaining time when available

    def test_fallback_uses_elapsed_when_no_remaining(self):
        from backend.main import _compile_resume_context

        context = {
            "current_exercise": "plank",
            "reps_this_set": 0,
            "total_reps": 0,
            "time_remaining_sec": None,
            "elapsed_active_sec": 180,
            "pause_count": 1,
            "last_correction": None,
        }

        with patch("backend.main._langfuse") as mock_lf:
            mock_lf.get_prompt.side_effect = Exception("langfuse unavailable")
            result = _compile_resume_context(context)

        assert isinstance(result, str)
        assert "3" in result  # 180s → "~3 minutes in"
