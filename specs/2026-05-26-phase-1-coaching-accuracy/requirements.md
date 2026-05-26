# Requirements: Phase 1 — Coaching Accuracy

## Goal
Make the AI coach more accurate and trustworthy during a session so that a parent with 10 minutes gets the same quality coaching as someone with a personal trainer.

## In scope
- Improve exercise detection accuracy (reduce false positives in rep counting)
- More precise, concise form feedback (timing and specificity of corrections)
- Advanced pose estimation for common bodyweight movements (squat, push-up, plank)

## Out of scope / deferred
- **Expand exercise library** — deferred until the app is stable. Current 20+ movements remain unchanged.

## Decisions & constraints
**Prompt engineering first.** Accuracy improvements are pursued through Langfuse prompt updates before adding any new infrastructure or ML dependencies. If prompt changes hit a ceiling that requires a dedicated pose model (e.g. MediaPipe), that decision is revisited explicitly with a tech-stack update.

No new ML services are introduced without a deliberate decision: per `specs/tech-stack.md`, no external ML services for form analysis beyond Gemini multimodal.

Prompts are managed in Langfuse (`scripts/upload_prompts.py`). All changes go through a new prompt version, not in-code edits.

## Background
Phase 1 evals (PR #33) established three evaluators and 24 labeled cases:
- `eval_rep_count_accuracy` — ±1 tolerance on expected rep counts
- `eval_correction_specificity` — corrections must include a body-part keyword
- `eval_interruption_integrity` — `user_speech_interruptions` must equal `adk_interruption_count`

Failure taxonomy from trace analysis identified:
- **F-1** (fixed): interruption count inflation — resolved in PR #33
- **F-2**: rep false positives — non-exercise movement (adjusting camera, sitting down) increments rep count
- **F-3**: generic corrections — coach says "good form" or "keep it up" with no actionable body-part cue
- **F-4**: missing exercises — movements not in the system instruction are undetected or mis-classified (deferred)

The three in-scope items map to F-2 (rep accuracy), F-3 (correction specificity and pose depth), and the pose-quality dimension of F-3 for squat/push-up/plank specifically.
