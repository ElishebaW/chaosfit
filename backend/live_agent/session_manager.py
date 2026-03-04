"""Session state + Firestore persistence + adaptive block generation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from google import genai

from backend.firestore.schema import (
    EVENTS_SUBCOLLECTION,
    SESSIONS_COLLECTION,
    SessionDocument,
    SessionEvent,
    utc_now_iso,
)
from backend.routines import AdaptiveContext, generate_next_unknown_time_block, load_exercise_library
from .form_feedback_prompt import build_next_block_prompt

try:
    from google.cloud import firestore
except Exception:  # pragma: no cover - optional in local dev
    firestore = None


@dataclass
class SessionState:
    session_id: str
    parent_id: str | None = None
    started_at: str = field(default_factory=utc_now_iso)
    ended_at: str | None = None
    status: str = "active"
    time_remaining_sec: int | None = None
    recent_form_score: float | None = None
    recent_fatigue: float | None = None
    exercise_history: list[str] = field(default_factory=list)
    live_model: str = "unknown"


class SessionManager:
    def __init__(self) -> None:
        self._mem: dict[str, SessionState] = {}
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "chaos-fit")
        self._project = project
        self._firestore = firestore.Client(project=project) if firestore else None
        self._vertex = genai.Client(
            vertexai=True,
            project=project,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
        )
        self._library = load_exercise_library()

    def start_session(
        self,
        *,
        session_id: str,
        parent_id: str | None,
        time_remaining_sec: int | None,
        live_model: str,
    ) -> SessionState:
        state = SessionState(
            session_id=session_id,
            parent_id=parent_id,
            time_remaining_sec=time_remaining_sec,
            live_model=live_model,
        )
        self._mem[session_id] = state
        self._upsert_session_doc(state)
        return state

    def get(self, session_id: str) -> SessionState:
        if session_id not in self._mem:
            raise KeyError(f"Unknown session_id: {session_id}")
        return self._mem[session_id]

    def append_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        state = self.get(session_id)
        if "exercise_id" in payload and isinstance(payload["exercise_id"], str):
            state.exercise_history.append(payload["exercise_id"])
        if "form_score" in payload:
            state.recent_form_score = _as_float(payload.get("form_score"))
        if "fatigue" in payload:
            state.recent_fatigue = _as_float(payload.get("fatigue"))
        if "time_remaining_sec" in payload:
            state.time_remaining_sec = _as_int(payload.get("time_remaining_sec"))

        if not self._firestore:
            return

        event = SessionEvent(ts=utc_now_iso(), event_type=event_type, payload=payload)
        (
            self._firestore.collection(SESSIONS_COLLECTION)
            .document(session_id)
            .collection(EVENTS_SUBCOLLECTION)
            .add(event.to_dict())
        )

    def complete_session(self, session_id: str) -> None:
        state = self.get(session_id)
        state.status = "completed"
        state.ended_at = utc_now_iso()
        self._upsert_session_doc(state)

    def generate_next_block(self, session_id: str, *, time_remaining_sec: int | None = None) -> dict[str, Any]:
        state = self.get(session_id)
        remaining = time_remaining_sec if time_remaining_sec is not None else (state.time_remaining_sec or 120)

        vertex_block = self._generate_next_block_with_vertex(
            time_remaining_sec=remaining,
            recent_form_score=state.recent_form_score,
            recent_fatigue=state.recent_fatigue,
            exercise_history=state.exercise_history,
        )
        if vertex_block is not None:
            return vertex_block

        fallback = generate_next_unknown_time_block(
            history=state.exercise_history,
            ctx=AdaptiveContext(
                time_remaining_sec=remaining,
                recent_form_score=state.recent_form_score,
                recent_fatigue=state.recent_fatigue,
                prefer_low_impact=True,
            ),
            block_duration_sec=min(remaining, 120),
            library=self._library,
        )
        return {
            "name": fallback.name,
            "mode": fallback.mode,
            "duration_sec": fallback.duration_sec,
            "items": [
                {
                    "exercise_id": item.exercise_id,
                    "prescription": item.prescription,
                    "coaching_hint": item.coaching_hint,
                }
                for item in fallback.items
            ],
            "voice_script": fallback.voice_script,
            "source": "deterministic_fallback",
        }

    def _generate_next_block_with_vertex(
        self,
        *,
        time_remaining_sec: int,
        recent_form_score: float | None,
        recent_fatigue: float | None,
        exercise_history: list[str],
    ) -> dict[str, Any] | None:
        prompt = build_next_block_prompt(
            time_remaining_sec=time_remaining_sec,
            recent_form_score=recent_form_score,
            recent_fatigue=recent_fatigue,
            exercise_history=exercise_history,
        )
        try:
            response = self._vertex.models.generate_content(
                model=os.getenv("NEXT_BLOCK_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            text = getattr(response, "text", None)
            if not text:
                return None
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return None
            parsed["source"] = "vertex_ai"
            return parsed
        except Exception:
            return None

    def _upsert_session_doc(self, state: SessionState) -> None:
        if not self._firestore:
            return

        doc = SessionDocument(
            session_id=state.session_id,
            parent_id=state.parent_id,
            status=state.status,
            started_at=state.started_at,
            ended_at=state.ended_at,
            time_remaining_sec=state.time_remaining_sec,
            live_model=state.live_model,
        )
        self._firestore.collection(SESSIONS_COLLECTION).document(state.session_id).set(doc.to_dict(), merge=True)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
