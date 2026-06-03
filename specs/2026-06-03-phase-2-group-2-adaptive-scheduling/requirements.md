# Requirements: Phase 2 Group 2 — Mid-session Adaptive Scheduling

## Goal
A parent with 10 minutes still gets a complete, sensible workout even when interruptions eat into planned time.

## In scope

- `remaining_time_sec()` on `SessionState` — already shipped in Group 1 PR review fix; referenced here as the foundation
- `should_reschedule(session_state) -> bool` in `adaptive_scheduler.py` — returns `True` when remaining active time has drifted > 20% from the current plan's remaining block time
- `rebuild_remaining_plan(session_state, remaining_sec) -> RoutinePlan` — trims/reorders unstarted blocks to fit remaining time; always preserves cooldown block
- Trigger reschedule logic after each block completes and on every resume — replace `session_state.routine_plan` when `should_reschedule()` returns `True`
- Langfuse trace for each reschedule event: log old plan duration, new plan duration, trigger (block-end or resume), remaining blocks

## Out of scope / deferred

- Fatigue and form-score input to rescheduling — Group 3 owns fatigue signal detection; adaptive scheduler uses it in Group 4
- Cross-session scheduling — Phase 4 (multi-session tracking)
- Frontend timer sending `duration_minutes` to backend — nice-to-have; `remaining_time_sec()` handles the None case gracefully

## Decisions & constraints

**`RoutinePlan` is frozen (`tuple[RoutineBlock, ...]`).** `rebuild_remaining_plan()` must produce a new `RoutinePlan` — it cannot mutate the existing one. `SessionState.routine_plan` (a dict) is replaced in place.

**`remaining_time_sec()` is already on `SessionState`** (landed in PR #44). Group 2 builds directly on it — no re-implementation needed.

**`adaptive_scheduler.py` already exists** with `recommend_next_block()` and `AdaptiveContext`. Group 2 extends it with two new functions; it does not replace existing logic.

**20% drift threshold** — if a 10-minute session has been active for 3 minutes but the remaining plan is 9 minutes of blocks, that's a 80% overrun; reschedule. Tunable constant, not hardcoded magic number.

**Cooldown block is always preserved** — trim main blocks first, never the cooldown. If only the cooldown fits, that's the plan.

**Langfuse for tracing.** Reschedule events traced with `@observe` consistent with existing `_trace_*` pattern in `session_manager.py`.

## Background

Phase 2 Group 1 shipped contextual interruption recovery (coach re-enters with exercise + rep context). `paused_at`, `total_pause_time_seconds`, and `elapsed_active_sec()` are now accurate. The infrastructure for computing remaining time is in place — Group 2 adds the scheduling logic that acts on it.

The adaptive scheduler at `backend/routines/adaptive_scheduler.py` has `recommend_next_block()` which selects the next exercise. Group 2 adds a higher-level layer: deciding whether the remaining block plan is still viable and replacing it if not.
