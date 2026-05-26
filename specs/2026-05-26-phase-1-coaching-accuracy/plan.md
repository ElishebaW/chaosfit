# Plan: Phase 1 — Coaching Accuracy

Each group is a shippable unit. Complete in order.

## Group 1 — Rep Count Accuracy (F-2)

Reduce false positives where non-exercise movement (camera adjustment, sitting down, fidgeting) is counted as a rep.

1. Export recent Langfuse traces where `rep_delta > 0` and review the video context windows to catalogue false-positive patterns.
2. Update `coach-system-instruction` and `coach-system-instruction-native-audio` in Langfuse: add explicit guidance that a rep requires a full range-of-motion cycle for the active exercise, and that incidental movement (hands near face, body shift without load) should not increment.
3. Extend `evals/dataset.json` `rep_count_accuracy_cases` with labeled cases that cover at least two false-positive patterns (e.g. camera adjust during push-ups, sitting between sets).
4. Run `evals/run_evals.py` locally; upload revised prompt version via `scripts/upload_prompts.py` and iterate until `eval_rep_count_accuracy` passes all cases.

## Group 2 — Form Feedback Specificity (F-3)

Ensure every correction names a body part and describes the corrective action, not just encouragement.

1. Review `correction_specificity_cases` in `evals/dataset.json` and trace samples where the coach gave generic feedback ("good job", "keep it up") to confirm failure patterns.
2. Update `coach-system-instruction` in Langfuse: require that every form correction follow the pattern `[body part] + [what to change]` (e.g. "lower your hips", "tuck your elbows in"). Generic praise is allowed but must not substitute for a correction when form is off.
3. Add labeled cases to `evals/dataset.json` `correction_specificity_cases` targeting the observed generic-feedback patterns.
4. Run `eval_correction_specificity` locally; iterate prompt until all new cases pass. Upload via `scripts/upload_prompts.py`.

## Group 3 — Pose Depth for Core Movements (squat, push-up, plank)

Give the coach richer pose cues for the three highest-frequency bodyweight movements so corrections are more precise.

1. For each of squat, push-up, and plank: document the 3–5 most common form errors and the specific landmarks Gemini multimodal can observe (knee tracking, hip hinge, elbow angle, core engagement visible via torso line).
2. Update `coach-system-instruction` in Langfuse with a per-exercise form guide section covering these landmarks and their acceptable ranges.
3. Add `correction_specificity_cases` for each of the three movements with cases that cover the common errors documented in step 1.
4. Run evals locally to confirm new pose-cue cases pass. Upload prompt version via `scripts/upload_prompts.py`.
5. Do a manual live session for each of the three movements and confirm corrections name landmarks rather than giving generic feedback.
