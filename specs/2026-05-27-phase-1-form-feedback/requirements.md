# Requirements: Phase 1 — Form Feedback

## Goal
Make the AI coach deliver corrections that are timely and specific enough that a parent with 10 minutes gets the same quality coaching as someone with a personal trainer.

## In scope
- More precise, concise form feedback — corrections fire at the right moment, name a body part, and describe the corrective action

## Out of scope / deferred
- **Rep count false positive reduction** — deferred; separate branch/iteration
- **Expand exercise library** — deferred until app is stable
- Advanced pose estimation beyond prompt-level landmark cues for squat, push-up, plank (may be revisited if prompt changes hit a ceiling)

## Decisions & constraints
Both prompt and pose estimation logic changes are in scope. Prompt changes are the first lever; if they hit a ceiling, backend pose/detection code in `backend/live_agent/` is fair game.

All prompt changes go through Langfuse versioning (`scripts/upload_prompts.py`) — no in-code edits to prompt strings.

An eval gate is required before merge: changes to `backend/live_agent/` or `evals/` must pass `evals/run_evals.py` in CI.

No new external ML services are introduced without a deliberate tech-stack decision (per `specs/tech-stack.md`).

## Background
Phase 1 evals (PR #33) established `eval_correction_specificity` targeting failure type F-3: coach says "good form" or "keep it up" with no actionable body-part cue. The existing evaluator checks for a body-part keyword in corrections but does not yet measure timing (firing too early, too late, or repeated within the same rep window).

This spec adds timing precision and repetition avoidance as explicit requirements on top of the existing specificity gate.
