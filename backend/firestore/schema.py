"""Firestore schema helpers for ChaosFit live coaching sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


SESSIONS_COLLECTION = "live_sessions"
EVENTS_SUBCOLLECTION = "events"


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
