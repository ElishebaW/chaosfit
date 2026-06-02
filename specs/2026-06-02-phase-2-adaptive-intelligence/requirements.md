# Requirements: Phase 2 — Adaptive Intelligence

## Goal
Make sessions smarter mid-workout so a parent with 10 minutes still gets a complete, sensible workout even when interrupted.

## In scope

1. **Mid-session adaptive scheduling** — restructure remaining blocks when elapsed time + interruptions would blow the planned duration
2. **Fatigue signal detection** — derive fatigue from video/audio cues (Gemini-observed, not externally supplied)
3. **Dynamic difficulty adjustment** — rep/time scaling and exercise substitution based on live fatigue/form signals
4. **Smarter interruption recovery** — coach resumes with contextual re-entry (exercise, reps so far, time remaining, interruption count), not from the top

## Out of scope / deferred

- Pause/resume with full state recovery (UI side) — deferred to Phase 3 (UX Hardening)
- Pre-session energy level input — Phase 3 setup flow owns this
- Cross-session fatigue/recovery modeling — Phase 4 (multi-session tracking)

## Decisions & constraints

**`RoutinePlan` is frozen.** `RoutinePlan.blocks` is an immutable `tuple[RoutineBlock, ...]`. Adaptive scheduling must produce a **new `RoutinePlan`** from remaining blocks — it cannot mutate the existing one. The session-layer `routine_plan` dict in `SessionState` can be replaced in place.

**Fatigue signals are currently external.** `SessionState.recent_fatigue` (0–1) and `recent_form_score` (0–1) exist but must be supplied by an external caller today (`append_event()` payload). Phase 2 adds a Gemini-native path: prompt the coach to emit a structured fatigue observation as a tool call, which the backend converts to a `fatigue_update` event.

**Adaptive scheduler already exists.** `backend/routines/adaptive_scheduler.py` has `recommend_next_block()` and `generate_next_unknown_time_block()` with `AdaptiveContext`. Phase 2 extends this — it does not replace it.

**Binary fatigue filter today.** Current logic: fatigue ≥ 0.75 OR form ≤ 0.45 → low-impact filter. Phase 2 adds continuous scaling (rep/time adjustment) and substitution before reaching the hard filter.

**Evals gate is required.** A CI eval must pass before merging, covering at minimum: interruption re-entry quality and adaptive schedule correctness after N interruptions.

**Langfuse for prompts and evals.** New/modified prompts go into Langfuse (`upload_prompts.py`). Eval datasets built from real session traces, consistent with Phase 1 eval pattern.

## Background

Phase 1 shipped tracing, prompt management, and coaching accuracy improvements. The coaching agent now has reliable rep counting and concise form feedback. The interruption infrastructure (pause/resume state, `total_pause_time_seconds`, `total_interruptions`) is in place in `session_manager.py`. What's missing is the intelligence layer that uses those signals to restructure the session and re-engage the user contextually.
