# Plan: Phase 1 — Form Feedback

Each group is a shippable unit. Complete in order.

## Group 1 — Diagnose current feedback patterns
1. Query Firestore session documents to find recent corrections: note the rep count at correction time and whether the correction was specific (body part + action) or generic.
2. Cross-reference with Langfuse traces (where available) to identify timing failures: corrections that fire before a rep is complete, repeated corrections within the same set without a new error, corrections that arrive after the user has already moved on.
3. Document the top 3–5 failure patterns as comments in `evals/dataset.json` to inform new cases in Group 2.

## Group 2 — Prompt changes for timing and specificity
1. Update `coach-system-instruction` and `coach-system-instruction-native-audio` in Langfuse:
   - Require every form correction to follow `[body part] + [corrective action]` (e.g. "drop your hips", "tuck your elbows in").
   - Add explicit guidance: do not repeat the same correction within the same set unless the error persists after 2 reps.
   - Add timing constraint: corrections should fire at the transition point of a rep (top or bottom of range of motion), not mid-movement.
2. Upload revised prompt versions via `scripts/upload_prompts.py`.
3. Verify new prompt version appears linked to traces in Langfuse.

## Group 3 — Pose cues for squat, push-up, plank
1. For each of squat, push-up, and plank, document 3–5 common form errors and the observable landmarks Gemini multimodal can see (e.g. knee cave, hip hinge depth, elbow flare, core sag visible via torso line).
2. Add a per-exercise landmark guide section to `coach-system-instruction` in Langfuse covering acceptable ranges for each landmark.
3. If prompt-only changes are insufficient (landmark guidance does not change correction quality after one iteration), audit `backend/live_agent/` for any pose threshold or trigger logic that could be adjusted.

## Group 4 — Eval coverage and gate
1. Add `correction_specificity_cases` to `evals/dataset.json` covering:
   - Timing failures: correction fires too early (mid-rep), correction repeated without new error
   - Landmark-specific cases for squat, push-up, and plank errors from Group 3 step 1
2. Run `evals/run_evals.py` locally; iterate on prompt and/or backend logic until all new cases pass.
3. Confirm CI runs `evals/run_evals.py` on PRs touching `backend/live_agent/` or `evals/` (see `.github/workflows/ci.yml`).
