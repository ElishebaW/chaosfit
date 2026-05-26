"""Regression tests: Firestore write failures must not disable the report client.

Before fix: every exception handler in SessionManager did self._firestore = None,
permanently destroying the client and causing /reports to 503 for the rest of the
process lifetime.

After fix: write errors are logged; get_firestore_client() keeps returning the
original client so the report endpoint stays alive.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_manager_with_failing_firestore():
    """Build a SessionManager whose Firestore client raises on every write."""
    failing_collection = MagicMock()
    failing_collection.document.return_value.set.side_effect = RuntimeError("network error")
    failing_collection.document.return_value.collection.return_value.add.side_effect = RuntimeError("network error")

    mock_client = MagicMock()
    mock_client.collection.return_value = failing_collection

    with patch.dict("os.environ", {"ENABLE_FIRESTORE": "false"}):
        from backend.live_agent.session_manager import SessionManager

        mgr = SessionManager()

    # Inject the failing client directly — bypasses the ENABLE_FIRESTORE guard
    mgr._firestore = mock_client
    return mgr, mock_client


@pytest.fixture(autouse=True)
def _clear_module_cache():
    """Reload session_manager so each test gets a clean import."""
    import importlib
    import backend.live_agent.session_manager as sm_mod
    importlib.reload(sm_mod)
    yield


class TestFirestoreClientStaysAliveAfterWriteFailure:
    def test_append_event_failure_keeps_client(self):
        mgr, mock_client = _make_manager_with_failing_firestore()
        mgr._mem["s1"] = _session_state("s1")

        mgr.append_event("s1", "exercise_update", {"rep_count": 5})

        assert mgr.get_firestore_client() is mock_client

    def test_upsert_session_doc_failure_keeps_client(self):
        mgr, mock_client = _make_manager_with_failing_firestore()
        state = _session_state("s2")
        mgr._mem["s2"] = state

        mgr._upsert_session_doc(state)

        assert mgr.get_firestore_client() is mock_client

    def test_write_summary_failure_keeps_client(self):
        from backend.firestore.schema import SessionSummary

        mgr, mock_client = _make_manager_with_failing_firestore()
        summary = SessionSummary(
            session_id="s3",
            user_id="u1",
            started_at="2026-01-01T00:00:00Z",
            ended_at="2026-01-01T00:10:00Z",
            exercise_type="push_up",
            rep_count=10,
            user_speech_interruptions=0,
            pause_count=0,
            total_pause_time_seconds=0.0,
            session_goal="test",
        )
        failing_summary_col = MagicMock()
        failing_summary_col.document.return_value.set.side_effect = RuntimeError("quota exceeded")
        mock_client.collection.return_value = failing_summary_col

        mgr._write_summary(summary)

        assert mgr.get_firestore_client() is mock_client

    def test_multiple_failures_keep_client(self):
        """Client survives repeated failures across different write paths."""
        mgr, mock_client = _make_manager_with_failing_firestore()
        mgr._mem["s4"] = _session_state("s4")

        for _ in range(3):
            mgr.append_event("s4", "exercise_update", {"rep_count": 1})
            mgr._upsert_session_doc(mgr._mem["s4"])

        assert mgr.get_firestore_client() is mock_client


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _session_state(session_id: str):
    from backend.live_agent.session_manager import SessionState
    return SessionState(session_id=session_id)
