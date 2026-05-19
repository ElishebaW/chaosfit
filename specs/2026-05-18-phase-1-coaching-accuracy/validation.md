# Validation: Phase 1 — Coaching Accuracy

## Done when
CI evals are green, rep counting is accurate within ±1 on a standard push-up and squat set, and form feedback quality is verified via Langfuse trace review.

## Checklist
- [ ] Failure taxonomy documented — at least 10 labeled failure cases in `evals/dataset.json`
- [ ] Rep count evaluator passes in CI: count within ±1 for a 10-rep push-up set and a 10-rep squat set
- [ ] Form feedback evaluator passes in CI: no generic corrections ("good job", "keep going") in traces; every correction names a body part or joint
- [ ] Correction timing: coach corrections fire after the triggering movement frame, not before (verified via trace timestamps)
- [ ] Pose estimation active for squat, push-up, plank: system instruction includes joint-angle guidance for all three
- [ ] Canvas overlays render joint markers for the three target exercises without visual regression on other exercises
- [ ] `evals` CI job runs coaching accuracy checks on every PR touching `backend/` or Langfuse prompt uploads
- [ ] `boundary-check` CI job still passes (no regressions)

## How to verify
1. **Evals**: `python -m evals.run_evals --ci` — should exit 0; failures print to stdout with trace IDs for inspection in Langfuse
2. **Rep count**: run `test/trace_harness.py --scenario clean_session --runs 5`; check Langfuse session summaries for `rep_count` accuracy
3. **Canvas overlays**: start the dev server (`uv run uvicorn backend.main:app --port 8080`), open in browser, perform a squat or push-up, confirm joint markers appear on canvas
4. **Correction specificity**: in Langfuse, filter `gemini_live_coach_turn` spans by session; read `output.text` — all corrections should name a specific body part
