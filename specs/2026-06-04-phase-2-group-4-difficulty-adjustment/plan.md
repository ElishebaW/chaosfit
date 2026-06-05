# Plan: Phase 2 Group 4 — Dynamic Difficulty Adjustment

Each group is a shippable unit. Complete in order.

## Group 1 — `adjust_difficulty` ADK tool + block mutation
1. Define `adjust_difficulty(direction: str, reason: str)` ADK tool in `backend/main.py` — `direction` is `"easier"` or `"harder"`.
2. Implement `_apply_difficulty_adjustment(session_id, direction)` — reads pending blocks from Firestore, mutates `reps` (±20–30%) and `rest_seconds` (±15s), writes back.
3. Wire tool call into the ADK session handler so the agent can invoke it mid-session.
4. Add `adjust_difficulty` to the coach system instruction in Langfuse (`coach-system-instruction-native-audio`) — when to call it, what triggers it.

## Group 2 — Passive inference (auto-trigger without explicit tool call)
1. Define performance signals: rep pace (reps delivered vs. expected in the time window) and form-quality signal (correction frequency from Langfuse trace data in the current session).
2. In `backend/main.py`, add a `_check_difficulty_signal(session_state)` function called on each rep-count update — returns `"easier"`, `"harder"`, or `None`.
3. If signal fires and no agent-initiated adjustment has happened in the last 60s, auto-call `_apply_difficulty_adjustment` and log it as a server-side trigger (not agent-initiated) in Langfuse.

## Group 3 — Langfuse tracing
1. Wrap each `_apply_difficulty_adjustment` call in a Langfuse span: `adjust_difficulty` span with attributes `direction`, `trigger` (`agent` or `server`), `rep_delta`, `rest_delta`, `session_id`.
2. Confirm spans appear under the session in Langfuse Sessions view alongside `report_fatigue` spans from Group 3.
3. Update `test/trace_harness.py` to include a difficulty-adjustment scenario and verify the span appears in Langfuse.
