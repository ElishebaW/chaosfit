# Plan: Phase 1 — AI Quality

Each group is a shippable unit. Complete in order — later groups depend on traces from earlier ones.

## Group 1 — LangSmith Setup & First Trace
1. Add `langsmith` to `pyproject.toml` dependencies via `uv add langsmith`
2. Add `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, and `LANGSMITH_PROJECT` as Cloud Run env vars and GitHub Actions secrets
3. Wrap the WebSocket message receipt handler in `backend/main.py` with `@traceable` — log message type, size, and timestamp per inbound message
4. Run a live session and confirm traces appear in the LangSmith dashboard before proceeding

## Group 2 — Instrument Remaining Backend Pipelines
1. **Video frame pipeline** — wrap frame capture → encode → send path; log `capturedAt`, encoded size, and server-side frame age at receipt (`main.py:273–415`)
2. **Session setup / routine planner** — trace inputs (duration, equipment, level) → generated plan; log which exercise blocks were selected
3. **Gemini Live API call (ADK)** — wrap the ADK coach-turn call; trace prompt context sent, response received, token counts, and latency
4. **Exercise detection / rep counting** — trace detected exercise type, confidence score, and rep delta per frame
5. **Interruption handling** — trace pause/resume events: session state snapshot before and after, time paused, context recovered
6. **Session summary generation** — trace final aggregation: reps, corrections, duration, any fields that were null or dropped

## Group 3 — Generate Trace Data
Two-phase data collection: scripted runs validate that every pipeline step traces correctly; real sessions surface the actual failure patterns worth measuring.

1. Write a test harness (pytest or standalone script) that drives the WebSocket session end-to-end: connects, sends synthetic frames, triggers an interruption, and completes a summary
2. Cover at least three scenarios: a clean full session, a session with one interruption, and a session with a misidentified exercise (e.g. a squat detected as a lunge)
3. Run the harness against staging 10 times — confirm every instrumented pipeline step produces a trace with no gaps
4. Run 10–15 real manual sessions on staging: vary lighting, movement pace, interruptions, and exercise types to expose edge cases that scripted runs won't generate
5. Review the LangSmith dashboard across both sets: tag runs by scenario, identify the top 3–5 failure patterns across the pipeline traces

## Group 4 — Eval Loop
1. Define eval dataset from the failure patterns identified in Group 3 — annotate a representative sample as ground truth
2. Write evaluators in Python targeting each identified gap using the LangSmith eval SDK
3. Wire evals into GitHub Actions CI: run on PRs touching `backend/main.py` or ADK/agent logic; fail the check on regression

## Group 5 — Coaching Accuracy Improvements
Scope and approach are determined by what the trace data reveals in Group 3. Do not plan specific fixes before that analysis.

Possible areas from the roadmap (prioritize based on observed failure frequency and user impact):
- Exercise detection accuracy and rep counting reliability
- Form feedback timing and specificity
- Pose estimation for common bodyweight movements
- Exercise library gaps

For each improvement tackled: reference the specific traces that motivated it, and verify against the evals from Group 4 before merging.
