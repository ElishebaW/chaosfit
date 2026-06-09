# Plan: Phase 3 — UX Hardening

Each group is a shippable unit. Complete in order.

## Group 1 — Guided pre-session setup flow
1. Add a setup screen in `backend/static/` (Vanilla JS, no framework) that collects: session goal, duration (minutes), available space, energy level (1–5).
2. On submit, send a `session_config` WebSocket message with the collected values before the ADK session starts.
3. In `backend/main.py`, handle `session_config` to set `state.planned_duration_minutes`, `state.prefer_low_impact`, and `state.level` on the `SessionState` before calling `session_manager.start_session`.
4. Pass `session_goal` from the setup form into the `COACH_SESSION_GOAL` context so the coach instruction includes the user's stated intent.

## Group 2 — Readable session summary UI
1. After `session_state:ended` is received by the client, fetch the summary from a new `GET /sessions/{session_id}/summary` FastAPI endpoint that reads from the `session_summaries` Firestore collection.
2. Render a post-workout card in `backend/static/` showing: exercise(s) completed, total reps, duration, correction count, pause count — styled with existing CSS, no new dependencies.
3. Add a "Share / Copy" button that copies a plain-text workout summary to the clipboard.
4. Ensure the card renders correctly when Firestore is disabled (fallback to in-memory `SessionState` data).

## Group 3 — Pause/resume full state recovery
1. Audit current pause/resume path in `backend/main.py` and `backend/live_agent/session_manager.py` — identify any rep count, form correction, or block index that is lost on pause/resume.
2. Persist `rep_count`, `cumulative_rep_count`, `form_corrections`, `current_block_index`, and `routine_plan` to Firestore on every pause event so state survives a page reload or reconnect.
3. On `resume`, restore in-memory `SessionState` from Firestore if the session exists but is not in `_mem` (reconnect path).
4. Add a unit test that simulates disconnect + reconnect and asserts rep count and block index are preserved.

## Group 4 — Visual feedback overlays
1. On each `exercise_update` event received by the client, draw a form-cue overlay on the existing Canvas element in `backend/static/app.js` — overlay shows the active exercise name and the most recent correction text.
2. Fade the overlay out after 3 seconds so it doesn't obstruct the video feed.
3. On `routine_plan_updated` events (from difficulty adjustment or reschedule), briefly flash the upcoming block name on canvas so the user knows the plan changed.
4. Test overlay rendering locally against the running server; confirm it doesn't interfere with the video stream.
