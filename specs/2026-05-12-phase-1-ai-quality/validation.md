# Validation: Phase 1 — AI Quality

## Done when
LangSmith evals are running in CI and rep counting is reliable enough that a user trusts the summary numbers.

## Checklist

### Observability
- [ ] Every instrumented pipeline step produces a trace for every session — no silent gaps in the LangSmith dashboard
- [ ] Traces include timing data sufficient to identify which step is slowest in a given session
- [ ] At least 10 scripted test harness runs and 10 real sessions are tagged and visible in LangSmith

### Evals
- [ ] Eval dataset is derived from observed trace failures, not assumptions — each example references a specific trace
- [ ] Evaluators target at least 3 distinct failure patterns identified from trace data
- [ ] Evals run automatically in CI on PRs touching `backend/main.py` or agent logic
- [ ] A known-bad change (e.g. removing stale frame rejection) causes the CI eval check to fail

### Coaching Accuracy
- [ ] The specific accuracy improvements shipped are justified by trace evidence (linked in the PR description)
- [ ] Rep counting error rate is low enough that a user would trust the post-session summary numbers — validated against real session traces

## How to verify
1. Open the LangSmith dashboard and confirm all pipeline steps have traces across both scripted and real sessions
2. Trigger a CI run on a PR that touches agent logic — confirm the eval check runs and passes
3. Introduce a deliberate regression (comment out a fix), re-run CI — confirm the eval check fails
4. Run a complete real session end-to-end and review the summary: rep counts should match what was actually performed
