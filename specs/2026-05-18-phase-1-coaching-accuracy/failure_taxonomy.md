# Failure Taxonomy: Phase 1 Coaching Accuracy

Derived from Langfuse export `1779197619660-lf-events-export-cmp46xh540135ad077y1avkp4.csv`
covering 6 trace-harness sessions across 3 scenarios (clean_session, session_with_interruption,
misidentified_exercise) run on 2026-05-18.

---

## F-1 · interruption_count conflated with correction_count

**Severity:** High — the session summary reports the wrong number for a user-facing metric.

**Evidence from traces:**

| Session | Actual pauses | summary.interruption_count | summary.correction_count |
|---|---|---|---|
| trace-clean_se-0-0aa703 | 0 | 1 | 1 |
| trace-session_-1-43cf81 | 1 (baby_crying) | 0 | 0 |
| trace-misident-2-d9897f | 0 | 2 | 2 |

Pattern: `interruption_count == correction_count` always. Actual pause count is in
`pause_count` (correct) but `interruption_count` is populated from `state.total_interruptions`,
which is incremented by every form correction in `_process_exercise_update`
(`session_manager.py:238-239`), not by pause/resume events.

**Root cause:** `session_manager.py:238-239` incremented `state.total_interruptions` inside the
form-correction loop. The summary then used `state.total_interruptions` as `interruption_count`,
making it equal to the correction count rather than anything session-interruption-related.

**Fix (implemented):**
- Removed `state.total_interruptions` increment from the form-correction loop
- Renamed the summary parameter to `coach_interruption_count` — now takes the ADK
  `event.interrupted` count from `main.py` (times the model's speech was cut off mid-turn)
- `pause_count` remains a separate dedicated field for user-initiated pauses
- `interruption_count` in the session summary now correctly equals the number of ADK
  coach interruptions, which is independent of both form corrections and user pauses

---

## F-2 · total_pause_time_seconds always 0.0

**Severity:** Medium — pause duration data is silently dropped.

**Evidence:** All `interruption_handling` and `session_summary_generation` spans show
`total_pause_time_seconds=0.0` even after a real pause/resume cycle.

**Root cause:** `resume_session` adds `pause_duration_seconds` to the running total
(`session_manager.py:401`), but the caller in `main.py` likely passes `0.0` unconditionally.
The actual elapsed pause time (from `state.paused_at` to now) is not computed at resume time.

**Fix:** In the resume handler in `main.py`, compute
`pause_duration = (utc_now - state.paused_at).total_seconds()` and pass it to
`resume_session`.

---

## F-3 · No gemini_live_coach_turn spans — coach output not observable

**Severity:** High — blocks all correction-quality evals.

**Evidence:** No `gemini_live_coach_turn` generation spans appear in any session traces.
The `invoke_agent chaosfit_live_coach` AGENT span is present and succeeds, but no
child spans capture what the model said. In native-audio mode, the ADK does not produce
text `modelTurn` parts, so the harness receives only `session_state` events.

**Impact:** Cannot evaluate correction specificity, correction timing, or exercise
identification quality from traces alone. All coaching-quality evals require text
output from the model.

**Fix options (choose one):**
1. Run a parallel text-mode session (non-native-audio) for eval purposes to capture
   model text output, even if the live session uses audio.
2. Add server-side logging that extracts and records any structured coaching signals
   (exercise ID, correction text) emitted by the ADK before converting to audio.
3. Prompt Gemini to emit a structured JSON block alongside coaching audio, parse it
   server-side, and record it as a Langfuse generation span.

---

## F-4 · Rep count is client-reported, not server-verified

**Severity:** Medium — rep accuracy cannot be measured from traces.

**Evidence:** `exercise_detection` span `rep_count` comes directly from the client's
`exercise_update` message. The server does not compare this to any server-side detection.

**Impact:** The `rep_count` in traces is what the client claims, not what Gemini detected.
A rep-count accuracy eval using trace data alone tests nothing about the AI's counting ability.

**Note:** This is a known architecture characteristic (client reports its own counts), not
a new bug. It is captured here because it means rep-count evals require a test harness
that sends ground-truth video and then validates the model's counting, not the current
synthetic-frame harness.

---

## What the traces confirm is working

- Session state machine: `active → paused → resumed → ended` sequencing is correct
- `pause_count` field is accurate (1 for session_with_interruption, 0 for others)
- `exercise_type` and `rep_count` fields in session summaries are non-null and plumbed correctly
- `session_summary_generation` span fires for every completed session
- All tracing plumbing works after the `update_current_trace` fix (Run 2 shows zero ERROR spans)
