# Requirements: Phase 1 — Coaching Accuracy

## Goal
Make the AI coach more accurate and trustworthy during a session — so a parent with 10 minutes gets the same quality coaching as someone with a personal trainer.

## In scope
- **Exercise detection accuracy** — reduce false positives and miscounts in rep counting
- **Form feedback quality** — more precise, timely corrections; eliminate generic or mistimed cues
- **Advanced pose estimation** — richer pose analysis for squat, push-up, and plank (joint angles, depth, alignment)

## Out of scope / deferred
- **Expand exercise library** — adding movements beyond the current ~20; deferred until detection accuracy is reliable on existing exercises

## Decisions & constraints
1. **Eval-driven** — use observed Langfuse trace data to identify failure modes before changing anything; no prompt tuning based on guesses
2. **Prompt tuning only** — all improvements live in Langfuse-managed system instructions; no new pipeline code or external ML services
3. **Canvas overlays** — surface pose/detection data visually on the video feed (joint markers, alignment cues) alongside voice coaching; implemented in `app.js` using the Canvas API

## Background
Phase 1 evals infrastructure is complete: Langfuse tracing, prompt management, and the scripted trace harness are all in place. This work builds on those tools — traces reveal what to fix, prompts are how we fix it, evals confirm it worked.
