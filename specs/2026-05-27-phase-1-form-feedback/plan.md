# Plan: Phase 1 — Form Feedback

Each group is a shippable unit. Complete in order.

## Group 1 — Diagnose current feedback patterns ✓
1. ✓ Query Firestore session documents to find recent corrections: note the rep count at correction time and whether the correction was specific (body part + action) or generic.
2. ✓ Cross-reference with Langfuse traces (where available) to identify timing failures: corrections that fire before a rep is complete, repeated corrections within the same set without a new error, corrections that arrive after the user has already moved on.
3. ✓ Document the top 3–5 failure patterns as comments in `evals/dataset.json` to inform new cases in Group 2.

## Group 2 — Prompt changes for timing and specificity ✓ (PR #39, PR #40)
1. ✓ Updated `coach-system-instruction` and `coach-system-instruction-native-audio` in Langfuse:
   - Require every form correction to follow `[body part] + [corrective action]` (e.g. "drop your hips", "tuck your elbows in").
   - Correct form errors immediately as they happen — do not wait for a rep to complete (PR #39; replaced transition-point rule after conflict resolution in PR #40).
   - Do not repeat the same correction within the same set unless the error persists after 2 more reps.
2. ✓ Uploaded revised prompt versions via `scripts/upload_prompts.py`.
3. ✓ New prompt versions appear linked to traces in Langfuse.

## Group 3 — Pose cues for squat, push-up, plank ✓ (PR #40)
1. ✓ Documented 5 errors for air squat, 5 for push-up, 4 for plank — each with observable visual landmark and corrective phrase.
2. ✓ Added per-exercise landmark guide to `coach-system-instruction` (full) and `coach-system-instruction-native-audio` (abbreviated) in Langfuse.
3. ✓ Backend audit complete: `backend/live_agent/` has no pose thresholds or trigger logic — all detection is prompt-driven, no code changes needed.

## Group 4 — Eval coverage and gate ✓ (PR #40)
1. ✓ Added 13 new `correction_specificity_cases` to `evals/dataset.json`:
   - 2 repetition failure cases (same correction 3+ times)
   - 9 landmark-specific pass cases (squat ×4, push-up ×3, plank ×2)
   - 1 two-identical boundary case
2. ✓ `evals/run_evals.py` passes 39/39 locally; `eval_correction_specificity` extended with Counter-based repetition check.
3. ✓ CI runs `evals/run_evals.py --ci` on all PRs (confirmed in `.github/workflows/ci.yml`).
