# Validation: Phase 1 — Form Feedback

## Done when
Langfuse evals are running in CI and rep counting is reliable enough that a user trusts the summary numbers.

Specifically for this spec: `eval_correction_specificity` passes at ≥ 90% on all labeled cases (timing failures + squat/push-up/plank landmark cases). Corrections must name a body part and corrective action; no generic praise substitutes for a real correction when form is off. Timing and repetition failures are covered by eval cases and passing.

## Checklist
- [x] Firestore session data queried; top failure patterns documented in `evals/dataset.json`
- [x] `eval_correction_specificity` eval threshold defined and agreed (≥ 90%; 39/39 = 100%)
- [x] New eval cases added for timing failures (early trigger, repeated correction) and squat/push-up/plank landmark errors (PR #40)
- [x] `eval_correction_specificity` passes at or above the defined threshold on all new cases (39/39)
- [x] `eval_interruption_integrity` and `eval_rep_count_accuracy` continue to pass (no regression)
- [x] CI runs `evals/run_evals.py` on PRs touching `backend/live_agent/` or `evals/`
- [ ] Manual session: coach corrections on squat, push-up, and plank each name a body part and corrective action
- [ ] Manual session: no repeated correction observed within the same set unless the error recurred

## How to verify
```
# Run evals locally
uv run python evals/run_evals.py

# Upload a revised prompt version
uv run python scripts/upload_prompts.py

# Check CI
# Push a branch touching backend/live_agent/ or evals/ — CI runs evals/run_evals.py
# See .github/workflows/ci.yml for the eval step
```

Eval output must show all cases passing. A failure in any eval is a merge blocker.
