# Plan: Phase 1 — Coaching Accuracy

Each group is a shippable unit. Complete in order.

## Group 1 — Failure taxonomy from traces
1. Pull recent session traces from Langfuse (REST API or `langfuse-cli`) filtering on `exercise_detection` and `session_summary_generation` observations
2. Categorize failures: mislabeled exercise type, wrong rep count, double-counted reps, generic/mistimed corrections
3. Build eval dataset in `evals/datasets/coaching_accuracy.json` from 10–20 representative failure cases
4. Document the failure taxonomy in a short note — drives prompt changes in Group 2

## Group 2 — Prompt tuning: rep counting & form feedback
1. Update `coach-system-instruction` in Langfuse to tighten rep counting logic (e.g., explicit rules for what counts as a completed rep per exercise)
2. Update form feedback prompts (`coach-system-instruction`, `coach-system-instruction-native-audio`) to require specific, timed corrections — eliminate generic phrases like "good job" or "keep going"
3. Upload new versions via `scripts/upload_prompts.py`
4. Write evaluators in `evals/` targeting: (a) rep count accuracy within ±1, (b) correction specificity (no generic phrases), (c) correction timing (fires after visible movement, not before)
5. Run evals locally and confirm improvement over baseline; iterate on prompts until passing

## Group 3 — Advanced pose estimation for squat, push-up, plank
1. Extend `coach-system-instruction` with joint-angle guidance for the three target exercises: squat (hip/knee depth), push-up (elbow angle, back alignment), plank (hip height, shoulder stack)
2. Add canvas overlay rendering in `app.js`: draw joint markers and alignment lines on the live video canvas for the three target exercises
3. Wire Gemini response pose data to canvas draw calls — parse any structured pose output from model turns and translate to pixel coordinates
4. Test overlays locally against camera feed; confirm joint markers track movement correctly

## Group 4 — CI gate
1. Add coaching accuracy evals to the `evals` job in `.github/workflows/ci.yml` (alongside existing eval checks)
2. Confirm `boundary-check` job still passes with updated prompts (Check 2: Langfuse prompt fetch present)
3. Open PR; confirm all jobs green before merge
