# Plan: Phase 2 Group 2 — Mid-session Adaptive Scheduling

Each group is a shippable unit. Complete in order.

## Group 2 — Mid-session Adaptive Scheduling

1. ~~Add `remaining_time_sec()` to `SessionState`~~ — already shipped in PR #44 (Group 1 review fix). Skip.
2. Add `RESCHEDULE_DRIFT_THRESHOLD = 0.20` and `should_reschedule(session_state: SessionState) -> bool` to `backend/routines/adaptive_scheduler.py`. Returns `True` when `remaining_time_sec()` is not None and `abs(plan_remaining_sec - time_remaining) / max(plan_remaining_sec, 1) > RESCHEDULE_DRIFT_THRESHOLD`, where `plan_remaining_sec` is the summed `duration_sec` of unstarted blocks in `session_state.routine_plan`.
3. Add `rebuild_remaining_plan(session_state: SessionState, remaining_sec: int, current_block_index: int = 0) -> dict[str, Any]` to `adaptive_scheduler.py`. Slice blocks from `current_block_index` (unstarted only). Separate into cooldown vs. main; trim longest main blocks first (fewest removals, maximum variety) until total fits within `remaining_sec`; always preserve the cooldown block last. Return as a `routine_plan`-shaped dict matching the existing schema.
4. In `backend/live_agent/session_manager.py`, add `maybe_reschedule(session_id: str, *, trigger: str) -> bool` on `SessionManager` — calls `should_reschedule()`, and if `True`, calls `rebuild_remaining_plan()`, replaces `state.routine_plan`, traces the event, and returns `True`. Add `@observe(name="adaptive_reschedule")` trace logging `session_id`, `trigger`, `old_plan_duration_sec`, `new_plan_duration_sec`, `remaining_blocks`.
5. Wire `maybe_reschedule()` into `backend/main.py`: call with `trigger="resume"` in the resume event handler (after `resume_session()`), and call with `trigger="block-end"` wherever block advancement happens. Add unit tests in `test/test_adaptive_scheduling.py` for `should_reschedule` boundary values, `rebuild_remaining_plan` output shape and cooldown preservation, and the `maybe_reschedule` integration path.
