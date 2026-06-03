# Validation: Phase 2 Group 2 — Mid-session Adaptive Scheduling

## Done when

Adaptive scheduling logic is correct per tests AND a live manual test confirms the coach adjusts block durations after two interruptions.

## Checklist

- [ ] `should_reschedule()` returns `False` when remaining time is within 20% of plan remaining time
- [ ] `should_reschedule()` returns `True` when a 10-minute session has 8 minutes of blocks remaining after 6 minutes active + 3 minutes pause time
- [ ] `should_reschedule()` returns `False` when `remaining_time_sec()` is `None` (no planned duration)
- [ ] `rebuild_remaining_plan()` produces a plan whose total block `duration_sec` fits within `remaining_sec ± 30s`
- [ ] `rebuild_remaining_plan()` always includes a cooldown block as the last item
- [ ] `rebuild_remaining_plan()` returns a valid plan when only the cooldown fits (all main blocks trimmed)
- [ ] `maybe_reschedule()` replaces `session_state.routine_plan` when `should_reschedule()` returns `True`
- [ ] Langfuse shows an `adaptive_reschedule` span with `trigger`, `old_plan_duration_sec`, `new_plan_duration_sec`, and `remaining_blocks`
- [ ] Reschedule fires on resume after 2 interruptions in an integration test
- [ ] **Manual smoke test**: start a session, pause twice for 60s each, resume — confirm via Langfuse that a reschedule span appears and `new_plan_duration_sec < old_plan_duration_sec`

## How to verify

**Unit tests** (`test/test_adaptive_scheduling.py`): boundary values for `should_reschedule()`, output shape and cooldown preservation for `rebuild_remaining_plan()`, integration path through `maybe_reschedule()`.

**Langfuse trace check**: after the manual smoke test, open Langfuse → Sessions, find the session, confirm an `adaptive_reschedule` span exists with plausible duration values.

**CI**: existing test suite must stay green; new tests added in this group must pass.
