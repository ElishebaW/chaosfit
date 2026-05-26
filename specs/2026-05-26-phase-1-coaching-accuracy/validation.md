# Validation: Phase 1 — Coaching Accuracy

## Done when
All coaching accuracy evals pass in CI on every PR touching agent logic. No merge to `main` is allowed if any of the three evaluators fails.

## Checklist
- [ ] `eval_rep_count_accuracy` passes all cases including new false-positive patterns (±1 tolerance)
- [ ] `eval_correction_specificity` passes all cases including new squat/push-up/plank correction cases
- [ ] `eval_interruption_integrity` continues to pass (no regression from prompt changes)
- [ ] All 3 groups of evals run in CI (`evals/run_evals.py` exits 0 on a PR that touches `backend/live_agent/` or `evals/`)
- [ ] Manual session: at least one squat, one push-up, and one plank session completed — coach corrections name a body part and corrective action each time
- [ ] Manual session: no false rep increments observed during a camera adjustment or rest period between sets

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

Eval output should show all cases passing with no failures. Any failure is a merge blocker.
