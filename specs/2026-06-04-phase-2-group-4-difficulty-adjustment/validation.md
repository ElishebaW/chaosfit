# Validation: Phase 2 Group 4 — Dynamic Difficulty Adjustment

## Done when
In a live test, the coach visibly adjusts reps or rest time for an upcoming block based on observed performance — and Langfuse traces confirm the adjustment event.

## Checklist
- [ ] `adjust_difficulty` ADK tool is callable by the agent mid-session without error
- [ ] Calling `adjust_difficulty("easier", ...)` reduces reps by 20–30% and increases rest by ~15s on remaining blocks in Firestore
- [ ] Calling `adjust_difficulty("harder", ...)` increases reps by 20–30% and decreases rest by ~15s on remaining blocks
- [ ] Passive inference fires at least once in a simulated "high correction frequency" scenario without an explicit agent call
- [ ] Each adjustment (agent-initiated or server-initiated) produces an `adjust_difficulty` Langfuse span with `direction`, `trigger`, `rep_delta`, `rest_delta`, `session_id`
- [ ] Spans appear under the correct session in Langfuse Sessions view alongside `report_fatigue` spans
- [ ] `test/trace_harness.py` difficulty-adjustment scenario produces the expected span and passes

## How to verify
1. Run `test/trace_harness.py` — confirm the difficulty-adjustment scenario exits cleanly and the span appears in Langfuse.
2. Start a live session, let the agent run two blocks, then manually trigger a "I'm exhausted" signal — confirm the coach calls `adjust_difficulty("easier", ...)` and the next block has reduced reps.
3. In Langfuse → Sessions, open the session and confirm both `report_fatigue` and `adjust_difficulty` spans are present and attributed to the correct session ID.
