# Requirements: Phase 1 — AI Quality

## Goal
Make the AI coach more accurate and trustworthy during a session, and give us the tooling to measure it — so a parent with 10 minutes gets the same quality coaching as someone with a personal trainer.

## In scope

### Agent Observability — LangSmith Tracing
Trace each workflow element independently so timing, inputs, and failures are visible per component:
- WebSocket message receipt — type, size, timestamp per inbound message
- Video frame pipeline — capture → encode → send; include `capturedAt` and server-side frame age
- Session setup / routine planner — inputs to generated plan; which exercise blocks were selected
- Gemini Live API call (ADK) — every coach turn: prompt context, response, tokens, latency
- Exercise detection / rep counting — exercise type, confidence, rep delta per frame
- Interruption handling — pause/resume events: session state before/after, time paused, context recovered
- Session summary generation — final aggregation: reps, corrections, duration, dropped state

### Evals (data-driven, after traces are collected)
- Define eval dataset from trace-observed failures — not pre-assumed gaps
- Write evaluators targeting the specific gaps traces reveal
- Run evals in CI on PRs touching agent logic

### Coaching Accuracy
- Improve exercise detection accuracy (reduce false positives in rep counting)
- More precise, concise form feedback (timing and specificity of corrections)
- Advanced pose estimation for common bodyweight movements (squat, push-up, plank)
- Expand exercise library beyond current 20+ movements

## Out of scope / deferred
Nothing deferred — all Phase 1 items are in scope.

## Decisions & constraints
- **Tracing tool:** LangSmith — trace ADK/Gemini calls, build eval datasets, run regressions in CI
- **AI calls go through ADK only** — do not call the Gemini REST API directly; all instrumentation wraps the ADK layer
- **Evals are evidence-driven** — no eval is written before trace data exists to justify it; observed failures define the dataset
- **Frontend stays dependency-free** — coaching accuracy improvements happen server-side (Python/ADK); no frontend framework changes
- **No video storage** — frame traces capture metadata only (size, age, confidence), never raw pixel data

## Background
Phase 0 delivered a stable, deployed app with working CI/CD and latency telemetry. Phase 1 builds the observability layer on top of that foundation. The core architectural decision (from the roadmap): traces first, evals second — real session data drives what gets measured, not assumptions about where the model fails.
