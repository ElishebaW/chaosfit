"""Session state + Firestore persistence + adaptive block generation."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from google import genai

from backend.firestore.schema import (
    EVENTS_SUBCOLLECTION,
    SESSIONS_COLLECTION,
    SESSION_SUMMARIES_COLLECTION,
    SessionDocument,
    SessionEvent,
    SessionSummary,
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
    pause_reason: str | None = None
    paused_at: str | None = None
    resumed_at: str | None = None
    time_remaining_sec: int | None = None
    recent_form_score: float | None = None
    recent_fatigue: float | None = None
    exercise_history: list[str] = field(default_factory=list)
    current_exercise: str | None = None
    rep_count: int = 0
    form_corrections: list[str] = field(default_factory=list)
    live_model: str = "unknown"
    total_interruptions: int = 0  # Track all interruptions including coach corrections
    cumulative_rep_count: int = 0  # Track total reps across session
    coach_interruptions: int = 0  # Track coach-initiated interruptions specifically
    pause_count: int = 0  # Track number of pauses during session
    total_pause_time_seconds: float = 0.0  # Track total pause time in seconds
    planned_duration_minutes: int | None = None
    equipment_available: tuple[str, ...] = ()
    prefer_low_impact: bool = False
    level: str | None = None
    routine_plan: dict[str, Any] | None = None


class SessionManager:
    def __init__(self) -> None:
        self._mem: dict[str, SessionState] = {}
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "chaos-fit")
        self._project = project
        self._firestore = None
        if firestore and _env_flag("ENABLE_FIRESTORE", default=False):
            try:
                self._firestore = firestore.Client(project=project)
                logging.info(f"Firestore client initialized for project: {project}")
            except Exception as e:
                logging.error(f"Failed to initialize Firestore client: {e}")
                self._firestore = None
        else:
            logging.warning("Firestore disabled or library not available")
        try:
            self._vertex = genai.Client(
                vertexai=os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() == "true",
                project=project,
                location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
            )
        except Exception as e:
            logging.warning(f"Failed to initialize GenAI client: {e}")
            self._vertex = None
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
        try:
            self._upsert_session_doc(state)
        except Exception:
            self._firestore = None
        return state

    def get(self, session_id: str) -> SessionState:
        if session_id not in self._mem:
            raise KeyError(f"Unknown session_id: {session_id}")
        return self._mem[session_id]

    def append_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        state = self.get(session_id)
        
        logging.debug(f"Processing event {event_type} for session {session_id}: {payload}")
        
        # Handle exercise_update events specifically
        if event_type == "exercise_update":
            self._process_exercise_update(state, payload)
        else:
            # Process other event types
            self._process_generic_event(state, payload)
                
        if "form_score" in payload:
            state.recent_form_score = _as_float(payload.get("form_score"))
        if "fatigue" in payload:
            state.recent_fatigue = _as_float(payload.get("fatigue"))
        if "time_remaining_sec" in payload:
            state.time_remaining_sec = _as_int(payload.get("time_remaining_sec"))

        if "duration_minutes" in payload:
            state.planned_duration_minutes = _as_int(payload.get("duration_minutes"))
        if "equipment_available" in payload and isinstance(payload.get("equipment_available"), list):
            state.equipment_available = tuple(str(e) for e in payload.get("equipment_available") or [])
        if "prefer_low_impact" in payload:
            state.prefer_low_impact = bool(payload.get("prefer_low_impact"))
        if "level" in payload:
            raw_level = payload.get("level")
            state.level = str(raw_level).strip() if raw_level is not None and str(raw_level).strip() else None
        if "routine_plan" in payload and isinstance(payload.get("routine_plan"), dict):
            state.routine_plan = payload.get("routine_plan")

        if not self._firestore:
            logging.debug(f"Firestore disabled, skipping event write for session {session_id}")
            return

        event = SessionEvent(ts=utc_now_iso(), event_type=event_type, payload=payload)
        try:
            result = (
                self._firestore.collection(SESSIONS_COLLECTION)
                .document(session_id)
                .collection(EVENTS_SUBCOLLECTION)
                .add(event.to_dict())
            )
            logging.info(f"Event written to Firestore: {event_type} for session {session_id}")
        except Exception as e:
            logging.error(f"Failed to write event to Firestore: {e}")
            # Fail-open in local/dev environments where Firestore is not enabled.
            self._firestore = None
    
    def _process_exercise_update(self, state: SessionState, payload: dict[str, Any]) -> None:
        """Process exercise update events with structured data."""
        
        # Track exercise ID and type
        exercise_id = payload.get("exercise_id")
        exercise_type = payload.get("exercise_type")
        
        if exercise_id and isinstance(exercise_id, str):
            # Only add to history if it's a new exercise (different from current)
            if exercise_id != state.current_exercise:
                state.exercise_history.append(exercise_id)
                logging.debug(f"New exercise: {exercise_id}")
            state.current_exercise = exercise_id
        elif exercise_type and isinstance(exercise_type, str):
            # Use exercise_type as fallback if no exercise_id
            if exercise_type != state.current_exercise:
                state.exercise_history.append(exercise_type)
                logging.debug(f"New exercise type: {exercise_type}")
            state.current_exercise = exercise_type
            
        # Track rep counts
        rep_count = payload.get("rep_count")
        if rep_count is not None:
            rep_count_int = _as_int(rep_count)
            if rep_count_int is not None and rep_count_int > 0:
                # For exercise updates, rep_count is typically the cumulative count
                # If it's a delta (small number), add to cumulative; if it's large, treat as new total
                if rep_count_int <= 50:  # Assume it's a delta addition
                    state.cumulative_rep_count += rep_count_int
                    state.rep_count = rep_count_int  # Current set reps
                else:  # Treat as new total
                    state.cumulative_rep_count = rep_count_int
                    state.rep_count = rep_count_int
                logging.debug(f"Updated rep count: +{rep_count_int} (total: {state.cumulative_rep_count})")
            
        # Track form corrections
        form_corrections = payload.get("form_corrections")
        if isinstance(form_corrections, list):
            new_corrections = []
            for correction in form_corrections:
                correction_str = str(correction).strip()
                if correction_str and correction_str not in state.form_corrections:
                    state.form_corrections.append(correction_str)
                    new_corrections.append(correction_str)
                    # Each new form correction counts as an interruption/coaching intervention
                    state.coach_interruptions += 1
                    state.total_interruptions += 1
                    logging.debug(f"Form correction interruption (total: {state.total_interruptions})")
            if new_corrections:
                logging.debug(f"Added {len(new_corrections)} form corrections")
                
        # Track explicit interruptions (from tool response interruption flag)
        if payload.get("interruption") is True:
            state.total_interruptions += 1
            state.coach_interruptions += 1
            logging.debug(f"Explicit coach interruption (total: {state.total_interruptions})")
    
    def _process_generic_event(self, state: SessionState, payload: dict[str, Any]) -> None:
        """Process generic events (legacy support)."""
        
        # Legacy exercise tracking
        if "exercise_id" in payload and isinstance(payload["exercise_id"], str):
            exercise_id = payload["exercise_id"]
            state.exercise_history.append(exercise_id)
            state.current_exercise = exercise_id
            logging.info(f"Updated exercise to {exercise_id} for session {state.session_id}")
            
        if "rep_count" in payload:
            rep_count = _as_int(payload.get("rep_count"))
            if rep_count is not None:
                state.rep_count += rep_count
                state.cumulative_rep_count += rep_count
                logging.info(f"Added {rep_count} reps to session {state.session_id} (total: {state.cumulative_rep_count})")
            
        if "form_corrections" in payload:
            corrections = payload.get("form_corrections")
            if isinstance(corrections, list):
                new_corrections = []
                for correction in corrections:
                    correction_str = str(correction).strip()
                    if correction_str and correction_str not in state.form_corrections:
                        state.form_corrections.append(correction_str)
                        new_corrections.append(correction_str)
                if new_corrections:
                    logging.info(f"Added {len(new_corrections)} form corrections to session {state.session_id}")
                    
        if "exercise_type" in payload and isinstance(payload["exercise_type"], str):
            state.current_exercise = payload["exercise_type"]
            logging.info(f"Updated exercise type to {payload['exercise_type']} for session {state.session_id}")
            
        # Track interruptions
        if payload.get("interruption") is True:
            state.total_interruptions += 1
            state.coach_interruptions += 1
            logging.info(f"Coach interruption detected for session {state.session_id} (total: {state.total_interruptions}, coach: {state.coach_interruptions})")

    def complete_session(self, session_id: str) -> None:
        state = self.get(session_id)
        if state.status == "ended":
            return
        state.status = "ended"
        state.ended_at = utc_now_iso()
        state.pause_reason = None
        self._upsert_session_doc(state)
        self.append_event(session_id, "session_state", {"status": "ended"})

    def record_session_summary(
        self,
        session_id: str,
        *,
        user_id: str,
        exercise_type: str | None = None,
        rep_count: int | None = None,
        interruption_count: int = 0,
        form_corrections: list[str] | None = None,
        session_goal: str | None = None,
    ) -> None:
        try:
            state = self.get(session_id)
            session_goal = session_goal or os.getenv("COACH_SESSION_GOAL")
            
            # Use accumulated state data as primary source, fallback to provided parameters
            final_exercise_type = exercise_type or state.current_exercise
            final_rep_count = rep_count if rep_count is not None else state.cumulative_rep_count
            final_interruption_count = interruption_count if interruption_count > 0 else state.total_interruptions
            final_form_corrections = form_corrections if form_corrections else state.form_corrections
            
            # Validate state before creating summary
            if state.status != "ended":
                logging.warning(f"Recording summary for session {session_id} but status is '{state.status}', not 'ended'")
                # Set status to ended if not already ended
                state.status = "ended"
                state.ended_at = utc_now_iso()
            
            summary = SessionSummary(
                session_id=session_id,
                user_id=user_id or state.parent_id,
                started_at=state.started_at,
                ended_at=state.ended_at or utc_now_iso(),
                exercise_type=final_exercise_type,
                rep_count=final_rep_count,
                interruption_count=final_interruption_count,
                form_corrections=tuple(final_form_corrections),
                session_goal=session_goal,
                pause_count=state.pause_count,
                total_pause_time_seconds=state.total_pause_time_seconds,
            )
            
            # Log summary details for debugging
            logging.info(f"Creating session summary for {session_id}: "
                        f"exercise={final_exercise_type}, "
                        f"reps={final_rep_count}, "
                        f"interruptions={final_interruption_count}, "
                        f"corrections={len(final_form_corrections)}, "
                        f"pauses={state.pause_count}, "
                        f"total_pause_time={state.total_pause_time_seconds}s")
            
            self._write_summary(summary)
        except Exception as e:
            logging.error(f"Failed to record session summary for {session_id}: {e}")
            # Don't re-raise the exception - let the caller handle it

    def get_firestore_client(self):
        return self._firestore

    def pause_session(self, session_id: str, *, reason: str = "manual_pause") -> SessionState:
        state = self.get(session_id)
        if state.status == "ended":
            return state
        state.status = "paused"
        state.pause_reason = reason
        state.paused_at = utc_now_iso()
        state.pause_count += 1  # Increment pause count
        self._upsert_session_doc(state)
        self.append_event(
            session_id,
            "session_state",
            {"status": "paused", "reason": reason, "paused_at": state.paused_at, "pause_count": state.pause_count},
        )
        return state

    def resume_session(self, session_id: str, pause_duration_seconds: float = 0.0) -> SessionState:
        state = self.get(session_id)
        if state.status == "ended":
            return state
        state.status = "active"
        state.pause_reason = None
        state.resumed_at = utc_now_iso()
        state.total_pause_time_seconds += pause_duration_seconds  # Add to total pause time
        self._upsert_session_doc(state)
        self.append_event(
            session_id,
            "session_state",
            {"status": "resumed", "resumed_at": state.resumed_at, "pause_duration_seconds": pause_duration_seconds, "total_pause_time_seconds": state.total_pause_time_seconds},
        )
        return state

    def can_accept_media(self, session_id: str) -> bool:
        state = self.get(session_id)
        return state.status == "active"

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
                prefer_low_impact=state.prefer_low_impact,
                equipment_available=state.equipment_available,
                level=state.level,
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
        if not self._vertex:
            return None
            
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
        try:
            result = self._firestore.collection(SESSIONS_COLLECTION).document(state.session_id).set(doc.to_dict(), merge=True)
            logging.info(f"Session document upserted: {state.session_id}")
        except Exception as e:
            logging.error(f"Failed to upsert session document: {e}")
            # Fail-open if API is disabled or credentials are not configured.
            self._firestore = None

    def _write_summary(self, summary: SessionSummary) -> None:
        if not self._firestore:
            return
        try:
            result = self._firestore.collection(SESSION_SUMMARIES_COLLECTION).document(summary.session_id).set(summary.to_dict(), merge=True)
            logging.info(f"Session summary written: {summary.session_id}")
        except Exception as e:
            logging.error(f"Failed to write session summary: {e}")
            self._firestore = None


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


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
