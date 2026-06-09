"""Session state + Firestore persistence + adaptive block generation."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from google import genai
from langfuse import get_client as _lf_client, observe, propagate_attributes

from backend.firestore.schema import (
    EVENTS_SUBCOLLECTION,
    SESSIONS_COLLECTION,
    SESSION_SUMMARIES_COLLECTION,
    SessionDocument,
    SessionEvent,
    SessionSummary,
    utc_now_iso,
)
from backend.routines import AdaptiveContext, generate_next_unknown_time_block, load_exercise_library, rebuild_remaining_plan, should_reschedule
from .form_feedback_prompt import build_next_block_prompt

try:
    from google.cloud import firestore
except Exception:  # pragma: no cover - optional in local dev
    firestore = None


@observe(name="session_setup")
def _trace_session_setup(session_id: str, parent_id: str | None, time_remaining_sec: int | None, live_model: str) -> dict[str, Any]:
    with propagate_attributes(session_id=session_id, user_id=parent_id):
        return {"session_id": session_id, "parent_id": parent_id, "time_remaining_sec": time_remaining_sec, "live_model": live_model}


@observe(name="routine_planner")
def _trace_routine_plan(session_id: str, time_remaining_sec: int, exercise_history: list[str], source: str, block_name: str | None) -> dict[str, Any]:
    with propagate_attributes(session_id=session_id):
        return {"session_id": session_id, "time_remaining_sec": time_remaining_sec, "exercise_history": exercise_history, "source": source, "block_name": block_name}


@observe(name="exercise_detection")
def _trace_exercise_update(session_id: str, exercise_id: str | None, rep_count: int | None, cumulative_reps: int, new_corrections: int, interruption: bool) -> dict[str, Any]:
    with propagate_attributes(session_id=session_id):
        return {"session_id": session_id, "exercise_id": exercise_id, "rep_count": rep_count, "cumulative_reps": cumulative_reps, "new_corrections": new_corrections, "interruption": interruption}


@observe(name="interruption_handling")
def _trace_interruption(session_id: str, event_type: str, reason: str | None, pause_count: int, total_pause_time_seconds: float) -> dict[str, Any]:
    with propagate_attributes(session_id=session_id):
        return {"session_id": session_id, "event_type": event_type, "reason": reason, "pause_count": pause_count, "total_pause_time_seconds": total_pause_time_seconds}


@observe(name="fatigue_update")
def _trace_fatigue_update(session_id: str, fatigue_level: float, confidence: str, observed_cues: list[str]) -> dict[str, Any]:
    with propagate_attributes(session_id=session_id):
        return {"session_id": session_id, "fatigue_level": fatigue_level, "confidence": confidence, "observed_cues": observed_cues}


@observe(name="adjust_difficulty")
def _trace_difficulty_adjustment(session_id: str, direction: str, trigger: str, rep_delta: int, rest_delta_sec: int, blocks_mutated: int) -> dict[str, Any]:
    with propagate_attributes(session_id=session_id):
        return {
            "session_id": session_id,
            "direction": direction,
            "trigger": trigger,
            "rep_delta": rep_delta,
            "rest_delta_sec": rest_delta_sec,
            "blocks_mutated": blocks_mutated,
        }


@observe(name="adaptive_reschedule")
def _trace_adaptive_reschedule(session_id: str, trigger: str, old_plan_duration_sec: int, new_plan_duration_sec: int, remaining_blocks: int) -> dict[str, Any]:
    with propagate_attributes(session_id=session_id):
        return {
            "session_id": session_id,
            "trigger": trigger,
            "old_plan_duration_sec": old_plan_duration_sec,
            "new_plan_duration_sec": new_plan_duration_sec,
            "remaining_blocks": remaining_blocks,
        }


@observe(name="session_summary_generation")
def _trace_session_summary(session_id: str, exercise_type: str | None, rep_count: int | None, user_speech_interruptions: int, correction_count: int, pause_count: int, total_pause_time_seconds: float) -> dict[str, Any]:
    with propagate_attributes(session_id=session_id):
        return {
            "session_id": session_id,
            "exercise_type": exercise_type,
            "rep_count": rep_count,
            "user_speech_interruptions": user_speech_interruptions,  # times user spoke while coach was mid-sentence
            "pause_count": pause_count,                               # user-initiated workout pauses
            "correction_count": correction_count,
            "total_pause_time_seconds": total_pause_time_seconds,
        }


def _elapsed_seconds(iso_ts: str) -> float:
    """Seconds elapsed since an ISO timestamp. Returns 0.0 on parse failure."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
    except (ValueError, TypeError):
        return 0.0


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
    current_block_index: int = 0
    last_difficulty_adjustment_at: str | None = None
    session_goal: str | None = None

    def elapsed_active_sec(self) -> float:
        """Wall-clock seconds minus accumulated pause time."""
        return max(0.0, _elapsed_seconds(self.started_at) - self.total_pause_time_seconds)

    def remaining_time_sec(self) -> int | None:
        """Remaining seconds based on planned duration. None if duration is unknown."""
        if self.planned_duration_minutes is None:
            return None
        return max(0, int(self.planned_duration_minutes * 60 - self.elapsed_active_sec()))

    def contextual_resume_summary(self) -> dict[str, Any]:
        return {
            "current_exercise": self.current_exercise,
            "reps_this_set": self.rep_count,
            "total_reps": self.cumulative_rep_count,
            "time_remaining_sec": self.remaining_time_sec(),
            "elapsed_active_sec": int(self.elapsed_active_sec()),
            "pause_count": self.pause_count,
            "last_correction": self.form_corrections[-1] if self.form_corrections else None,
        }


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
        # Restore from a previous paused session if recovery data exists in Firestore
        recovery = self._restore_session_from_firestore(session_id)
        if recovery:
            state.cumulative_rep_count = int(recovery.get("cumulative_rep_count") or 0)
            state.rep_count = int(recovery.get("rep_count") or 0)
            state.form_corrections = list(recovery.get("form_corrections") or [])
            state.current_block_index = int(recovery.get("current_block_index") or 0)
            state.routine_plan = recovery.get("routine_plan")
            state.current_exercise = recovery.get("current_exercise")
            state.exercise_history = list(recovery.get("exercise_history") or [])
            state.planned_duration_minutes = _as_int(recovery.get("planned_duration_minutes"))
            state.session_goal = recovery.get("session_goal")
            state.total_pause_time_seconds = float(recovery.get("total_pause_time_seconds") or 0.0)
            state.pause_count = int(recovery.get("pause_count") or 0)
            state.total_interruptions = int(recovery.get("total_interruptions") or 0)
            state.coach_interruptions = int(recovery.get("coach_interruptions") or 0)
            state.recent_fatigue = _as_float(recovery.get("recent_fatigue"))
            state.recent_form_score = _as_float(recovery.get("recent_form_score"))
            state.last_difficulty_adjustment_at = recovery.get("last_difficulty_adjustment_at")
            logging.info("Restored session %s from Firestore recovery data", session_id)
        self._mem[session_id] = state
        _trace_session_setup(session_id, parent_id, time_remaining_sec, live_model)
        self._upsert_session_doc(state)
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
        elif event_type == "fatigue_update":
            self._process_fatigue_update(state, payload)
        elif event_type == "difficulty_adjustment":
            self._process_difficulty_adjustment(state, payload)
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
        if "goal" in payload and payload.get("goal"):
            state.session_goal = str(payload["goal"])

        # Passive signal check — runs after all payload mutations so fatigue/plan are current.
        # Skip after explicit agent-triggered adjustments to avoid double-firing.
        if event_type != "difficulty_adjustment":
            self._maybe_auto_adjust_difficulty(session_id, state)

        # Passive signal check — runs after all payload mutations so fatigue/plan are current.
        # Skip after explicit agent-triggered adjustments to avoid double-firing.
        if event_type != "difficulty_adjustment":
            self._maybe_auto_adjust_difficulty(session_id, state)

        if not self._firestore:
            logging.debug(f"Firestore disabled, skipping event write for session {session_id}")
            return

        event = SessionEvent(ts=utc_now_iso(), event_type=event_type, payload=payload)
        try:
            (
                self._firestore.collection(SESSIONS_COLLECTION)
                .document(session_id)
                .collection(EVENTS_SUBCOLLECTION)
                .add(event.to_dict())
            )
            logging.info(f"Event written to Firestore: {event_type} for session {session_id}")
        except Exception as e:
            logging.error(f"Failed to write event to Firestore: {e}")
    
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
        new_correction_count = 0
        form_corrections = payload.get("form_corrections")
        if isinstance(form_corrections, list):
            for correction in form_corrections:
                correction_str = str(correction).strip()
                if correction_str and correction_str not in state.form_corrections:
                    state.form_corrections.append(correction_str)
                    new_correction_count += 1
            if new_correction_count:
                logging.debug(f"Added {new_correction_count} form corrections")

        # Track explicit interruptions (from tool response interruption flag)
        interruption = payload.get("interruption") is True
        if interruption:
            state.total_interruptions += 1
            state.coach_interruptions += 1
            logging.debug(f"Explicit coach interruption (total: {state.total_interruptions})")

        _trace_exercise_update(
            state.session_id,
            state.current_exercise,
            _as_int(payload.get("rep_count")),
            state.cumulative_rep_count,
            new_correction_count,
            interruption,
        )
    
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

    def _apply_difficulty_adjustment(self, state: SessionState, direction: str, reason: str, trigger: str = "agent") -> dict[str, Any]:
        """Mutate reps_min/reps_max and rest_seconds on all blocks after the current one."""
        factor = 0.75 if direction == "easier" else 1.25
        rest_delta = 15 if direction == "easier" else -15
        if not state.routine_plan or not state.routine_plan.get("blocks"):
            _trace_difficulty_adjustment(state.session_id, direction, trigger, 0, rest_delta, 0)
            return {"mutated_blocks": 0, "direction": direction}
        blocks = state.routine_plan["blocks"]
        pending = blocks[state.current_block_index + 1:]
        if not pending:
            _trace_difficulty_adjustment(state.session_id, direction, trigger, 0, rest_delta, 0)
            return {"mutated_blocks": 0, "direction": direction}
        rep_delta = 0
        rep_delta_captured = False
        for block in pending:
            for item in (block.get("items") or []):
                presc = item.get("prescription")
                if not isinstance(presc, dict):
                    continue
                if presc.get("type") == "reps":
                    if "reps_min" in presc:
                        presc["reps_min"] = max(1, round(presc["reps_min"] * factor))
                    if "reps_max" in presc:
                        old_max = presc["reps_max"]
                        new_max = max(1, round(old_max * factor))
                        if not rep_delta_captured:
                            rep_delta = new_max - old_max
                            rep_delta_captured = True
                        presc["reps_max"] = new_max
                if "rest_seconds" in presc:
                    presc["rest_seconds"] = max(10, presc["rest_seconds"] + rest_delta)
        state.last_difficulty_adjustment_at = utc_now_iso()
        _trace_difficulty_adjustment(state.session_id, direction, trigger, rep_delta, rest_delta, len(pending))
        self._write_routine_plan(state)
        logging.info(
            "adjust_difficulty session=%s direction=%s trigger=%s blocks_mutated=%d reason=%r",
            state.session_id, direction, trigger, len(pending), reason,
        )
        return {"mutated_blocks": len(pending), "direction": direction, "reason": reason}

    def _process_difficulty_adjustment(self, state: SessionState, payload: dict[str, Any]) -> None:
        direction = str(payload.get("direction", ""))
        reason = str(payload.get("reason", ""))
        if direction not in ("easier", "harder"):
            logging.warning("_process_difficulty_adjustment: invalid direction %r for session %s", direction, state.session_id)
            return
        self._apply_difficulty_adjustment(state, direction, reason, trigger="agent")

    def _expected_reps_per_min(self, state: SessionState) -> float | None:
        """Derive expected reps/min from the current block's reps prescriptions. Returns None if unavailable."""
        if not state.routine_plan:
            return None
        blocks = state.routine_plan.get("blocks") or []
        if state.current_block_index >= len(blocks):
            return None
        block = blocks[state.current_block_index]
        duration_sec = block.get("duration_sec") or 0
        if not duration_sec:
            return None
        total_expected = sum(
            (p.get("reps_min", 0) + p.get("reps_max", 0)) / 2
            for item in (block.get("items") or [])
            for p in [item.get("prescription") or {}]
            if p.get("type") == "reps"
        )
        return (total_expected / (duration_sec / 60.0)) if total_expected > 0 else None

    def _check_difficulty_signal(self, state: SessionState) -> str | None:
        """Return 'easier', 'harder', or None based on passive performance signals."""
        # Fatigue-based: immediate trigger regardless of elapsed time
        if state.recent_fatigue is not None and state.recent_fatigue >= 0.7:
            return "easier"
        elapsed_sec = state.elapsed_active_sec()
        if elapsed_sec < 60:
            return None
        elapsed_min = elapsed_sec / 60.0
        # High correction rate over at least 2 minutes → ease off
        if elapsed_min >= 2.0 and len(state.form_corrections) / elapsed_min > 2.0:
            return "easier"
        # Ahead of expected rep pace with no corrections → push harder
        expected_rpm = self._expected_reps_per_min(state)
        if expected_rpm is not None:
            actual_rpm = state.cumulative_rep_count / elapsed_min
            if actual_rpm > expected_rpm * 1.5 and len(state.form_corrections) == 0:
                return "harder"
        return None

    def _maybe_auto_adjust_difficulty(self, session_id: str, state: SessionState) -> None:
        """Fire a server-side passive difficulty adjustment if signals warrant it."""
        if state.status != "active":
            return
        # Cooldown guard: don't auto-adjust more often than every 90 seconds
        if state.last_difficulty_adjustment_at:
            if _elapsed_seconds(state.last_difficulty_adjustment_at) < 90:
                return
        direction = self._check_difficulty_signal(state)
        if direction is None:
            return
        result = self._apply_difficulty_adjustment(state, direction, reason="server_passive_signal", trigger="server")
        logging.info(
            "Passive difficulty adjustment session=%s direction=%s blocks_mutated=%d",
            session_id, direction, result.get("mutated_blocks", 0),
        )

    def _process_fatigue_update(self, state: SessionState, payload: dict[str, Any]) -> None:
        fatigue_level = _as_float(payload.get("fatigue_level"))
        if fatigue_level is not None:
            state.recent_fatigue = fatigue_level
        confidence = str(payload.get("confidence", "unknown"))
        observed_cues = list(payload.get("observed_cues") or [])
        _trace_fatigue_update(state.session_id, fatigue_level or 0.0, confidence, observed_cues)
        logging.info(
            "Fatigue update session=%s level=%.2f confidence=%s cues=%s",
            state.session_id, fatigue_level or 0.0, confidence, observed_cues,
        )

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
        user_speech_interruptions: int = 0,
        form_corrections: list[str] | None = None,
        session_goal: str | None = None,
    ) -> None:
        try:
            state = self.get(session_id)
            session_goal = session_goal or state.session_goal or os.getenv("COACH_SESSION_GOAL")

            # Use accumulated state data as primary source, fallback to provided parameters
            final_exercise_type = exercise_type or state.current_exercise
            final_rep_count = rep_count if rep_count is not None else state.cumulative_rep_count
            # user_speech_interruptions = times the user spoke while the coach was mid-sentence
            # (ADK event.interrupted). pause_count = user-initiated workout pauses — separate field.
            final_user_speech_interruptions = user_speech_interruptions
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
                user_speech_interruptions=final_user_speech_interruptions,
                form_corrections=tuple(final_form_corrections),
                session_goal=session_goal,
                pause_count=state.pause_count,
                total_pause_time_seconds=state.total_pause_time_seconds,
            )
            
            # Log summary details for debugging
            logging.info(f"Creating session summary for {session_id}: "
                        f"exercise={final_exercise_type}, "
                        f"reps={final_rep_count}, "
                        f"interruptions={final_user_speech_interruptions}, "
                        f"corrections={len(final_form_corrections)}, "
                        f"pauses={state.pause_count}, "
                        f"total_pause_time={state.total_pause_time_seconds}s")
            
            _trace_session_summary(
                session_id,
                final_exercise_type,
                final_rep_count,
                final_user_speech_interruptions,
                len(final_form_corrections),
                state.pause_count,
                state.total_pause_time_seconds,
            )
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
        state.pause_count += 1
        _trace_interruption(session_id, "pause", reason, state.pause_count, state.total_pause_time_seconds)
        self._upsert_session_doc(state)
        self._write_full_session_state(state)
        self.append_event(
            session_id,
            "session_state",
            {"status": "paused", "reason": reason, "paused_at": state.paused_at, "pause_count": state.pause_count},
        )
        return state

    def resume_session(self, session_id: str, pause_duration_seconds: float | None = None) -> SessionState:
        state = self.get(session_id)
        if state.status == "ended":
            return state
        state.status = "active"
        state.pause_reason = None
        state.resumed_at = utc_now_iso()
        if pause_duration_seconds is None:
            pause_duration_seconds = _elapsed_seconds(state.paused_at) if state.paused_at else 0.0
        state.total_pause_time_seconds += pause_duration_seconds
        context = state.contextual_resume_summary()
        _trace_interruption(session_id, "resume", None, state.pause_count, state.total_pause_time_seconds)
        self._upsert_session_doc(state)
        self.append_event(
            session_id,
            "session_state",
            {
                "status": "resumed",
                "resumed_at": state.resumed_at,
                "pause_duration_seconds": pause_duration_seconds,
                "total_pause_time_seconds": state.total_pause_time_seconds,
                "resume_context": context,
            },
        )
        return state

    def maybe_reschedule(self, session_id: str, *, trigger: str) -> bool:
        """Rebuild unstarted blocks if actual time has drifted from plan. Resets current_block_index. Returns True if rescheduled."""
        state = self.get(session_id)
        time_remaining = state.remaining_time_sec()
        if not should_reschedule(
            routine_plan=state.routine_plan,
            time_remaining_sec=time_remaining,
            current_block_index=state.current_block_index,
        ):
            return False
        old_blocks = ((state.routine_plan or {}).get("blocks") or [])[state.current_block_index:]
        old_total = sum(b.get("duration_sec", 0) for b in old_blocks)
        new_plan = rebuild_remaining_plan(state.routine_plan, time_remaining, state.current_block_index)  # type: ignore[arg-type]
        new_blocks = new_plan.get("blocks") or []
        new_total = sum(b.get("duration_sec", 0) for b in new_blocks)
        state.routine_plan = new_plan
        state.current_block_index = 0  # new plan starts from the beginning
        _trace_adaptive_reschedule(session_id, trigger, old_total, new_total, len(new_blocks))
        logging.info(
            "Rescheduled session %s trigger=%s old=%ds new=%ds blocks=%d",
            session_id, trigger, old_total, new_total, len(new_blocks),
        )
        return True

    def advance_block(self, session_id: str) -> None:
        """Mark the current block as complete and advance to the next."""
        state = self.get(session_id)
        state.current_block_index += 1

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
            _trace_routine_plan(session_id, remaining, state.exercise_history, "vertex_ai", vertex_block.get("name"))
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
        block = {
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
        _trace_routine_plan(session_id, remaining, state.exercise_history, "deterministic_fallback", fallback.name)
        return block

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
            
        try:
            _prompt_obj = _lf_client().get_prompt("adaptive-block-request", label="production")
            prompt = _prompt_obj.compile(
                time_remaining_sec=str(time_remaining_sec),
                recent_form_score=json.dumps(recent_form_score),
                recent_fatigue=json.dumps(recent_fatigue),
                exercise_history=json.dumps(exercise_history[-8:]),
            )
        except Exception:
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
            self._firestore.collection(SESSIONS_COLLECTION).document(state.session_id).set(doc.to_dict(), merge=True)
            logging.info(f"Session document upserted: {state.session_id}")
        except Exception as e:
            logging.error(f"Failed to upsert session document: {e}")

    def _write_full_session_state(self, state: SessionState) -> None:
        """Persist recovery fields to Firestore on pause so a reconnect can restore them."""
        if not self._firestore:
            return
        try:
            self._firestore.collection(SESSIONS_COLLECTION).document(state.session_id).set(
                {
                    "recovery": {
                        "cumulative_rep_count": state.cumulative_rep_count,
                        "rep_count": state.rep_count,
                        "form_corrections": list(state.form_corrections),
                        "current_block_index": state.current_block_index,
                        "routine_plan": state.routine_plan,
                        "current_exercise": state.current_exercise,
                        "exercise_history": list(state.exercise_history),
                        "planned_duration_minutes": state.planned_duration_minutes,
                        "session_goal": state.session_goal,
                        "total_pause_time_seconds": state.total_pause_time_seconds,
                        "pause_count": state.pause_count,
                        "total_interruptions": state.total_interruptions,
                        "coach_interruptions": state.coach_interruptions,
                        "recent_fatigue": state.recent_fatigue,
                        "recent_form_score": state.recent_form_score,
                        "last_difficulty_adjustment_at": state.last_difficulty_adjustment_at,
                    }
                },
                merge=True,
            )
            logging.info("Session recovery state persisted for %s", state.session_id)
        except Exception as e:
            logging.error("Failed to persist session recovery state %s: %s", state.session_id, e)

    def _restore_session_from_firestore(self, session_id: str) -> dict | None:
        """Return persisted recovery fields for session_id, or None if unavailable."""
        if not self._firestore:
            return None
        try:
            doc = self._firestore.collection(SESSIONS_COLLECTION).document(session_id).get()
            if not doc.exists:
                return None
            return (doc.to_dict() or {}).get("recovery")
        except Exception as e:
            logging.error("Failed to read recovery state for %s: %s", session_id, e)
            return None

    def _write_routine_plan(self, state: SessionState) -> None:
        if not self._firestore or not state.routine_plan:
            return
        try:
            self._firestore.collection(SESSIONS_COLLECTION).document(state.session_id).set(
                {"routine_plan": state.routine_plan}, merge=True
            )
            logging.info("Routine plan persisted for session %s", state.session_id)
        except Exception as e:
            logging.error("Failed to persist routine_plan for session %s: %s", state.session_id, e)

    def _write_summary(self, summary: SessionSummary) -> None:
        if not self._firestore:
            return
        try:
            self._firestore.collection(SESSION_SUMMARIES_COLLECTION).document(summary.session_id).set(summary.to_dict(), merge=True)
            logging.info(f"Session summary written: {summary.session_id}")
        except Exception as e:
            logging.error(f"Failed to write session summary: {e}")


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
