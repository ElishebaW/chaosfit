# Validation: Phase 2 — Adaptive Intelligence

## Done when

A session interrupted twice still delivers a complete, sensible workout — AND a CI eval passes that verifies this programmatically before merging.

## Checklist

- [ ] `contextual_resume_summary()` returns correct fields (exercise, reps, time_remaining, pause_count) after a simulated pause/resume cycle
- [ ] Resume prompt rendered by the coach references the actual exercise and reps in progress — not a generic "let's continue"
- [ ] `remaining_time_sec()` returns accurate value accounting for pause time
- [ ] `should_reschedule()` returns `True` when a 10-minute session has 8 minutes of blocks remaining after 6 minutes of active + 3 minutes of pause time
- [ ] `rebuild_remaining_plan()` produces a plan whose total block `duration_sec` fits within `remaining_sec` ± 30s, and always includes a cooldown block
- [ ] Rescheduling is triggered on resume after 2 interruptions in an integration test
- [ ] `report_fatigue` ADK tool is callable by the coach and its payload is persisted to `SessionState.recent_fatigue`
- [ ] Langfuse shows a `fatigue_update` span when `report_fatigue` is called, with `fatigue_level` and `observed_cues`
- [ ] `compute_difficulty_modifier()` returns 0.6 for `fatigue=0.9, form_score=0.3` and 1.0 for `fatigue=0.1, form_score=0.9`
- [ ] Block `duration_sec` is reduced by the modifier when `recent_fatigue ≥ 0.75`
- [ ] A high-intensity exercise is substituted with a low-impact variant when modifier < 0.75
- [ ] **CI eval passes**: an eval dataset of ≥ 5 interrupted session traces (2+ pauses each) is run in CI; evaluator scores coach resume utterance for contextual accuracy (references correct exercise + reps); pass threshold ≥ 80%

## How to verify

**Unit tests** (`test/`): add tests for `contextual_resume_summary()`, `remaining_time_sec()`, `should_reschedule()`, `rebuild_remaining_plan()`, and `compute_difficulty_modifier()` with boundary values.

**Integration test**: run `test/trace_harness.py` with a new scenario `interrupted_x2` — pause twice, verify Langfuse shows rescheduling spans and the resume prompt references the correct exercise.

**CI eval**: add a step in `.github/workflows/ci.yml` (after existing eval step) that runs `scripts/run_evals.py --dataset phase2-interruption-recovery` and fails if pass rate < 80%. Dataset built from real Langfuse session traces with 2+ pauses.

**Manual smoke test**: start a session, pause twice for 60s each, resume — confirm the coach re-entry utterance names the exercise you were doing and remaining time is plausible.
