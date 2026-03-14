"""Firestore schema helpers for ChaosFit live coaching sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from google.cloud import firestore

SESSIONS_COLLECTION = "live_sessions"
EVENTS_SUBCOLLECTION = "events"
SESSION_SUMMARIES_COLLECTION = "session_summaries"

@dataclass(frozen=True)
class SessionDocument:
    session_id: str
    parent_id: str | None
    status: str
    started_at: str
    ended_at: str | None
    time_remaining_sec: int | None
    live_model: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "parent_id": self.parent_id,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "time_remaining_sec": self.time_remaining_sec,
            "live_model": self.live_model,
        }


@dataclass(frozen=True)
class SessionEvent:
    ts: str
    event_type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "event_type": self.event_type,
            "payload": self.payload,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    user_id: str | None
    started_at: str
    ended_at: str
    exercise_type: str | None
    rep_count: int | None
    interruption_count: int
    form_corrections: tuple[str, ...] = field(default_factory=tuple)
    session_goal: str | None = None
    pause_count: int = 0  # Number of pauses during session
    total_pause_time_seconds: float = 0.0  # Total pause time in seconds
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exercise_type": self.exercise_type,
            "rep_count": self.rep_count,
            "interruption_count": self.interruption_count,
            "form_corrections": list(self.form_corrections),
            "session_goal": self.session_goal,
            "pause_count": self.pause_count,
            "total_pause_time_seconds": self.total_pause_time_seconds,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SessionSummary":
        corrections = tuple(str(item) for item in data.get("form_corrections", []) or [])
        return SessionSummary(
            session_id=str(data["session_id"]),
            user_id=data.get("user_id"),
            started_at=str(data["started_at"]),
            ended_at=str(data["ended_at"]),
            exercise_type=data.get("exercise_type"),
            rep_count=_safe_int(data.get("rep_count")),
            interruption_count=int(data.get("interruption_count", 0)),
            form_corrections=corrections,
            session_goal=data.get("session_goal"),
            pause_count=int(data.get("pause_count", 0)),
            total_pause_time_seconds=float(data.get("total_pause_time_seconds", 0.0)),
            created_at=str(data.get("created_at") or utc_now_iso()),
        )


async def save_session(db: firestore.AsyncClient, session_id: str, user_id: str, session_data: dict):
    doc_ref = db.collection(SESSION_SUMMARIES_COLLECTION).document(session_id)
    await doc_ref.set({
        "user_id": user_id,
        "session_id": session_id,
        "exercise_type": session_data.get("exercise_type"),
        "rep_count": session_data.get("rep_count", 0),
        "interruption_count": session_data.get("interruption_count", 0),
        "form_corrections": session_data.get("form_corrections", []),
        "start_time": session_data.get("start_time"),
        "end_time": firestore.SERVER_TIMESTAMP,
    })

def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
