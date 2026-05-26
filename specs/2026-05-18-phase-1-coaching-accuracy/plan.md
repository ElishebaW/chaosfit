# Plan: Phase 1 — Coaching Accuracy

Each group is a shippable unit. Complete in order.

## Group 1 — Failure taxonomy from traces
- [x] Pull recent session traces from Langfuse filtering on `exercise_detection` and `session_summary_generation` observations
- [x] Categorize failures: wrong rep count, double-counted reps, false positives, generic corrections (→ F-1 through F-5 in `failure_taxonomy.md`)
- [x] Build eval dataset in `evals/dataset.json` — 27 cases across rep count, correction specificity, interruption integrity, and session summary
- [x] Document failure taxonomy in `failure_taxonomy.md` — F-5 (rep-count false positives) added in PR #36

## Group 2 — Prompt tuning: rep counting & form feedback
- [x] Update `coach-system-instruction` with rep counting guidance: full ROM required, incidental movement excluded (PR #36)
- [x] Update `coach-system-instruction-native-audio` with same rep counting guidance (PR #36)
- [ ] Upload new prompt versions to Langfuse (`set -a && source .env && set +a && uv run python scripts/upload_prompts.py`)
- [x] Write evaluators: `eval_rep_count_accuracy` (±1, zero-tolerance when expected=0), `eval_correction_specificity`, `eval_interruption_integrity`
- [x] 27/27 evals passing locally
- [ ] Form feedback prompt update: require `[body part] + [corrective action]` pattern, eliminate generic phrases — Group 2 follow-on

## Group 3 — Advanced pose estimation for squat, push-up, plank
- [ ] Extend `coach-system-instruction` with joint-angle guidance: squat (hip/knee depth), push-up (elbow angle, back alignment), plank (hip height, shoulder stack)
- [ ] Add canvas overlay rendering in `app.js`: draw joint markers and alignment lines for the three target exercises
- [ ] Wire Gemini response pose data to canvas draw calls — parse structured pose output from model turns and translate to pixel coordinates
- [ ] Test overlays locally against camera feed; confirm joint markers track movement correctly

## Group 4 — CI gate
- [ ] Add coaching accuracy evals to the `evals` job in `.github/workflows/ci.yml`
- [ ] Confirm `boundary-check` job still passes with updated prompts
- [ ] Open PR; confirm all jobs green before merge
