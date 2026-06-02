# Plan: Phase 2 — Adaptive Intelligence

Each group is a shippable unit. Complete in order.

## Group 1 — Smarter Interruption Recovery

1. Add a `contextual_resume_summary()` method to `SessionState` (`backend/live_agent/session_manager.py`) that returns a structured dict: current exercise, reps completed this set, total reps, time remaining, interruption count, and last form correction.
2. In `resume_session()`, call `contextual_resume_summary()` and attach the result to the resumed event payload so downstream code can access it.
3. Create a `coach-resume-context` Langfuse prompt that takes the summary dict and generates a coach re-entry utterance ("You were doing push-ups — 8 reps in. 4 minutes left. Let's pick back up."). Add to `scripts/upload_prompts.py`.
4. Wire the resume event to fetch and render the `coach-resume-context` prompt before the next coaching turn in `backend/main.py` WebSocket handler.

## Group 2 — Mid-session Adaptive Scheduling

1. Add `remaining_time_sec()` to `SessionState` — computes `planned_duration_minutes * 60 - (elapsed - total_pause_time_seconds)`. Returns `None` if duration is unknown.
2. Add `should_reschedule(session_state: SessionState) -> bool` to `backend/routines/adaptive_scheduler.py` — returns `True` when remaining time has drifted > 20% from the current plan's remaining block time.
3. Add `rebuild_remaining_plan(session_state: SessionState, remaining_sec: int) -> RoutinePlan` — takes the current `routine_plan` blocks that haven't started yet, trims/reorders to fit `remaining_sec`, returns a new frozen `RoutinePlan`. Preserve cooldown block; trim main blocks first.
4. In the session's block-advancement logic (`backend/main.py` or `session_manager.py`), call `should_reschedule()` after each block completes and after each resume. If `True`, call `rebuild_remaining_plan()` and replace `session_state.routine_plan`.
5. Trace the reschedule event in Langfuse: log old plan duration, new plan duration, trigger (block-end or resume), and remaining blocks.

## Group 3 — Fatigue Signal Detection

1. Add a `report_fatigue` ADK tool to the coaching agent (alongside existing tools in `backend/live_agent/`). Tool schema: `{ fatigue_level: float (0–1), confidence: str (low/medium/high), observed_cues: list[str] }`. The coach calls this tool when it observes cues (labored breathing, form degradation, slowed pace).
2. In the tool handler, call `session_state.append_event("fatigue_update", payload)` to feed the signal into existing `recent_fatigue` tracking.
3. Add Langfuse tracing for `fatigue_update` events: log `fatigue_level`, `confidence`, `observed_cues`, `session_id`.
4. Update the `coach-system-instruction` Langfuse prompt to include guidance on when and how to call `report_fatigue` — specific observable cues (pacing slowdown, breath audible in mic, 3+ form corrections in last 2 minutes).

## Group 4 — Dynamic Difficulty Adjustment

1. Add `compute_difficulty_modifier(session_state: SessionState) -> float` in `backend/routines/adaptive_scheduler.py` — returns a scalar (0.6–1.0) based on `recent_fatigue` and `recent_form_score`. Formula: `1.0 - 0.4 * max(fatigue, 1 - form_score)`, clamped to [0.6, 1.0].
2. Apply modifier in `recommend_next_block()` — scale `duration_sec` of selected `BlockItem`s by the modifier. Round to nearest 5s.
3. Add exercise substitution: if modifier < 0.75, replace the next high-intensity exercise with the closest low-impact variant from the existing library mapping in `adaptive_scheduler.py`.
4. Expose current difficulty modifier in the Langfuse trace for each block recommendation (log as `difficulty_modifier` attribute on the `recommend_next_block` span).
5. Update `coach-system-instruction` in Langfuse to tell the coach that block durations may have been shortened, and to acknowledge this to the user ("I've trimmed the next set — let's keep moving").
