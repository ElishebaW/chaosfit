"""Tests for Phase 2 Group 3: Fatigue Signal Detection."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.coach_agent.response_handler import report_fatigue
from backend.live_agent.session_manager import SessionManager, SessionState


def _make_state(**kwargs) -> SessionState:
    return SessionState(session_id="test-session", **kwargs)


def _make_manager() -> SessionManager:
    with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
        return SessionManager()


# ---------------------------------------------------------------------------
# report_fatigue tool function
# ---------------------------------------------------------------------------

class TestReportFatigue:
    def test_returns_success_status(self):
        result = report_fatigue(0.7, "high", ["labored breathing"], "s1")
        assert result["status"] == "success"

    def test_returns_fatigue_update_type(self):
        result = report_fatigue(0.5, "medium", [], "s1")
        assert result["type"] == "fatigue_update"

    def test_fatigue_level_preserved(self):
        result = report_fatigue(0.6, "medium", ["slowed pace"], "s1")
        assert result["fatigue_level"] == 0.6

    def test_clamps_below_zero(self):
        result = report_fatigue(-0.5, "low", [], "s1")
        assert result["fatigue_level"] == 0.0

    def test_clamps_above_one(self):
        result = report_fatigue(1.8, "high", [], "s1")
        assert result["fatigue_level"] == 1.0

    def test_observed_cues_preserved(self):
        cues = ["labored breathing", "hip sag worsening"]
        result = report_fatigue(0.8, "high", cues, "s1")
        assert result["observed_cues"] == cues

    def test_confidence_preserved(self):
        result = report_fatigue(0.4, "low", [], "s1")
        assert result["confidence"] == "low"

    def test_session_id_preserved(self):
        result = report_fatigue(0.5, "medium", [], "my-session")
        assert result["session_id"] == "my-session"

    def test_empty_cues_list(self):
        result = report_fatigue(0.3, "low", [], "s1")
        assert result["observed_cues"] == []

    def test_none_cues_becomes_empty_list(self):
        result = report_fatigue(0.3, "low", None, "s1")
        assert result["observed_cues"] == []

    def test_invalid_fatigue_level_returns_error(self):
        result = report_fatigue("not-a-number", "low", [], "s1")
        assert result["status"] == "error"
        assert "fatigue_level" in result["message"]

    def test_none_fatigue_level_returns_error(self):
        result = report_fatigue(None, "low", [], "s1")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

class TestReportFatigueToolRegistered:
    def test_report_fatigue_tool_in_agent(self):
        from backend.coach_agent.agent import agent
        from backend.coach_agent.response_handler import report_fatigue_tool
        assert report_fatigue_tool in agent.tools

    def test_emit_exercise_data_tool_still_present(self):
        from backend.coach_agent.agent import agent
        from backend.coach_agent.response_handler import emit_exercise_data_tool
        assert emit_exercise_data_tool in agent.tools


# ---------------------------------------------------------------------------
# append_event("fatigue_update") → state.recent_fatigue
# ---------------------------------------------------------------------------

class TestFatigueUpdateAppendEvent:
    def test_sets_recent_fatigue(self):
        mgr = _make_manager()
        state = _make_state()
        mgr._mem["test-session"] = state

        mgr.append_event("test-session", "fatigue_update", {
            "fatigue_level": 0.75,
            "confidence": "high",
            "observed_cues": ["labored breathing"],
            "session_id": "test-session",
        })

        assert state.recent_fatigue == 0.75

    def test_does_not_touch_rep_count(self):
        mgr = _make_manager()
        state = _make_state(rep_count=10, cumulative_rep_count=10)
        mgr._mem["test-session"] = state

        mgr.append_event("test-session", "fatigue_update", {"fatigue_level": 0.5})

        assert state.rep_count == 10
        assert state.cumulative_rep_count == 10

    def test_does_not_touch_form_corrections(self):
        mgr = _make_manager()
        state = _make_state(form_corrections=["keep your chest up"])
        mgr._mem["test-session"] = state

        mgr.append_event("test-session", "fatigue_update", {"fatigue_level": 0.6})

        assert state.form_corrections == ["keep your chest up"]

    def test_missing_fatigue_level_leaves_recent_fatigue_unchanged(self):
        mgr = _make_manager()
        state = _make_state(recent_fatigue=0.3)
        mgr._mem["test-session"] = state

        mgr.append_event("test-session", "fatigue_update", {"confidence": "low", "observed_cues": []})

        assert state.recent_fatigue == 0.3

    def test_overwrites_previous_fatigue(self):
        mgr = _make_manager()
        state = _make_state(recent_fatigue=0.2)
        mgr._mem["test-session"] = state

        mgr.append_event("test-session", "fatigue_update", {"fatigue_level": 0.9})

        assert state.recent_fatigue == 0.9


# ---------------------------------------------------------------------------
# _process_coach_tool_event routing
# ---------------------------------------------------------------------------

class TestProcessCoachToolEventRouting:
    @pytest.mark.asyncio
    async def test_fatigue_update_routes_to_append_event(self):
        from backend.main import _process_coach_tool_event

        fake_event = MagicMock()
        fake_event.tool_response = {
            "status": "success",
            "type": "fatigue_update",
            "fatigue_level": 0.7,
            "confidence": "high",
            "observed_cues": ["labored breathing"],
            "session_id": "s1",
        }

        mgr = MagicMock()
        await _process_coach_tool_event(fake_event, "s1", mgr)

        mgr.append_event.assert_called_once()
        args = mgr.append_event.call_args
        event_type = args.kwargs.get("event_type") or args.args[1]
        assert event_type == "fatigue_update"

    @pytest.mark.asyncio
    async def test_exercise_update_still_routes_correctly(self):
        from backend.main import _process_coach_tool_event

        fake_event = MagicMock()
        fake_event.tool_response = {
            "status": "success",
            "event": {"type": "exercise_update", "rep_count": 5, "session_id": "s1"},
        }

        mgr = MagicMock()
        await _process_coach_tool_event(fake_event, "s1", mgr)

        mgr.append_event.assert_called_once()
        args = mgr.append_event.call_args
        event_type = args.kwargs.get("event_type") or args.args[1]
        assert event_type == "exercise_update"

    @pytest.mark.asyncio
    async def test_error_response_is_ignored(self):
        from backend.main import _process_coach_tool_event

        fake_event = MagicMock()
        fake_event.tool_response = {"status": "error", "message": "bad input"}

        mgr = MagicMock()
        await _process_coach_tool_event(fake_event, "s1", mgr)

        mgr.append_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_tool_response_is_ignored(self):
        from backend.main import _process_coach_tool_event

        fake_event = MagicMock()
        fake_event.tool_response = None

        mgr = MagicMock()
        await _process_coach_tool_event(fake_event, "s1", mgr)

        mgr.append_event.assert_not_called()
