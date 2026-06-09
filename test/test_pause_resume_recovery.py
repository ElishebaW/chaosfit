"""Tests for Phase 3 Group 3: pause/resume full state recovery."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


from backend.live_agent.session_manager import SessionManager, SessionState


def _make_manager() -> SessionManager:
    with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
        return SessionManager()


def _make_manager_with_firestore() -> tuple[SessionManager, MagicMock]:
    mock_fs = MagicMock()
    mock_fs.collection.return_value.document.return_value.get.return_value.exists = False
    with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
        mgr = SessionManager()
    mgr._firestore = mock_fs
    return mgr, mock_fs


# ---------------------------------------------------------------------------
# _write_full_session_state
# ---------------------------------------------------------------------------

class TestWriteFullSessionState:
    def test_writes_recovery_block_to_firestore(self):
        mgr, mock_fs = _make_manager_with_firestore()
        state = SessionState(
            session_id="s1",
            cumulative_rep_count=25,
            rep_count=5,
            form_corrections=["keep chest up"],
            current_block_index=2,
            current_exercise="push_up",
            exercise_history=["push_up", "air_squat"],
            pause_count=1,
            total_pause_time_seconds=30.0,
            total_interruptions=3,
            coach_interruptions=2,
            recent_fatigue=0.6,
            recent_form_score=0.8,
        )
        mgr._write_full_session_state(state)
        mock_fs.collection.return_value.document.return_value.set.assert_called_once()
        call_args = mock_fs.collection.return_value.document.return_value.set.call_args
        recovery = call_args.args[0]["recovery"]
        assert recovery["cumulative_rep_count"] == 25
        assert recovery["form_corrections"] == ["keep chest up"]
        assert recovery["current_block_index"] == 2
        assert recovery["pause_count"] == 1
        assert recovery["exercise_history"] == ["push_up", "air_squat"]
        assert recovery["total_interruptions"] == 3
        assert recovery["recent_fatigue"] == 0.6
        assert recovery["last_difficulty_adjustment_at"] is None

    def test_skips_write_when_no_firestore(self):
        mgr = _make_manager()
        state = SessionState(session_id="s1")
        mgr._write_full_session_state(state)  # must not raise

    def test_pause_session_calls_write_full_state(self):
        mgr, mock_fs = _make_manager_with_firestore()
        state = SessionState(session_id="s1", status="active")
        mgr._mem["s1"] = state
        write_calls: list = []
        mgr._write_full_session_state = lambda s: write_calls.append(s.session_id)  # type: ignore
        mgr.pause_session("s1", reason="test")
        assert "s1" in write_calls


# ---------------------------------------------------------------------------
# _restore_session_from_firestore
# ---------------------------------------------------------------------------

class TestRestoreSessionFromFirestore:
    def test_returns_none_when_no_firestore(self):
        mgr = _make_manager()
        assert mgr._restore_session_from_firestore("s1") is None

    def test_returns_none_when_doc_does_not_exist(self):
        mgr, mock_fs = _make_manager_with_firestore()
        mock_fs.collection.return_value.document.return_value.get.return_value.exists = False
        assert mgr._restore_session_from_firestore("s1") is None

    def test_returns_recovery_dict_when_present(self):
        mgr, mock_fs = _make_manager_with_firestore()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "recovery": {"cumulative_rep_count": 30, "form_corrections": ["keep back straight"]}
        }
        mock_fs.collection.return_value.document.return_value.get.return_value = mock_doc
        result = mgr._restore_session_from_firestore("s1")
        assert result is not None
        assert result["cumulative_rep_count"] == 30


# ---------------------------------------------------------------------------
# start_session — reconnect restores state
# ---------------------------------------------------------------------------

class TestStartSessionRestoresState:
    def test_restores_rep_count_on_reconnect(self):
        mgr, mock_fs = _make_manager_with_firestore()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "recovery": {
                "cumulative_rep_count": 42,
                "rep_count": 7,
                "form_corrections": ["keep chest up"],
                "current_block_index": 1,
                "routine_plan": None,
                "current_exercise": "push_up",
                "planned_duration_minutes": 20,
                "session_goal": "cardio",
                "total_pause_time_seconds": 15.0,
                "pause_count": 2,
            }
        }
        mock_fs.collection.return_value.document.return_value.get.return_value = mock_doc
        # Also mock the set call (upsert_session_doc)
        mock_fs.collection.return_value.document.return_value.set = MagicMock()

        state = mgr.start_session(
            session_id="s1", parent_id="user1", time_remaining_sec=None, live_model="test"
        )
        assert state.cumulative_rep_count == 42
        assert state.current_block_index == 1
        assert state.form_corrections == ["keep chest up"]
        assert state.pause_count == 2
        assert state.session_goal == "cardio"

    def test_fresh_session_when_no_recovery_data(self):
        mgr, mock_fs = _make_manager_with_firestore()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {}  # no recovery key
        mock_fs.collection.return_value.document.return_value.get.return_value = mock_doc
        mock_fs.collection.return_value.document.return_value.set = MagicMock()

        state = mgr.start_session(
            session_id="s1", parent_id="user1", time_remaining_sec=None, live_model="test"
        )
        assert state.cumulative_rep_count == 0
        assert state.current_block_index == 0
        assert state.form_corrections == []
