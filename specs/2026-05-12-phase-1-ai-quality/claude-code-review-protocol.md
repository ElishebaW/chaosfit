# Specification: Agentic Code Review & Context Audit Protocol (v1.0.0)

**Target Environment:** ChaosFit Python/FastAPI backend, WebSocket session loop, event-driven trace/eval workflow  
**Author:** Backend Engineering / AI Operations  
**Review Target:** Multi-file Claude Code PRs, especially Phase 1 Group 4 eval-loop work

## Objective & Scope

This protocol defines mandatory verification steps for engineering leads reviewing pull requests generated autonomously or semi-autonomously by Claude Code. The goal is to detect non-syntax anomalies, structural regressions, context-blind architecture choices, weak tests, and boundary drift before code merges.

Use this protocol to review a multi-file agent PR for Phase 1 AI Quality work. The reviewer must validate the diff against the Phase 1 spec, the current roadmap decision to use Langfuse instead of LangSmith, and the locked architecture in `specs/tech-stack.md` and `docs/ARCHITECTURE.md`.

## Source of Truth

- PR spec: `specs/2026-05-12-phase-1-ai-quality/requirements.md`
- PR plan: `specs/2026-05-12-phase-1-ai-quality/plan.md`
- PR validation: `specs/2026-05-12-phase-1-ai-quality/validation.md`
- Current implementation decision: `specs/roadmap.md`
- Architecture guardrails: `docs/ARCHITECTURE.md`, `specs/tech-stack.md`, `specs/mission.md`

If these disagree, prefer the newer roadmap entry and code reality for Phase 1 Group 4:

- Use Langfuse, not LangSmith.
- Trace application-layer events, not every WebSocket message, audio chunk, or video frame.
- Evals must be derived from observed trace failures.

## Review Setup

Run these first and paste the output into the review notes:

```bash
git status --short
git branch --show-current
git diff --name-only origin/main...HEAD
git diff --stat origin/main...HEAD
```

The expected branch for this review is `feat/phase-1-group-4-eval-loop`. Any changed file outside these areas requires explicit justification in the PR description:

- `.github/workflows/ci.yml`
- `evals/**`
- `test/trace_harness.py`
- `backend/session_utils.py`
- `backend/main.py`
- `backend/live_agent/**`
- `backend/routines/**`
- `pyproject.toml`
- `backend/requirements.txt`
- `uv.lock`
- `specs/**`
- `README.md`

## Phase 1: Tool-Use & Context Log Audit

Before reviewing changed lines, evaluate whether the agent had the required system context. Reject the PR for context blindness if the agent modified a repository layer without reading the corresponding schema, interface, spec, or architecture file.

### Context Checklist

- Inspect the Claude Code session transcript or commit history for tool-use traces.
- Verify the agent read `specs/2026-05-12-phase-1-ai-quality/**` before changing eval, trace, or agent behavior.
- Verify the agent read `docs/ARCHITECTURE.md` and `specs/tech-stack.md` before changing backend boundaries.
- Verify the agent read `backend/firestore/schema.py` before changing persisted session summary fields.
- Verify the agent read `backend/live_agent/session_manager.py` before changing session lifecycle, pause/resume, exercise tracking, or summary behavior.
- Verify the agent read `.github/workflows/ci.yml` before changing CI, eval triggers, or test commands.

### Context Detection Commands

Use these commands to identify the context files the PR should have considered:

```bash
git log -p --stat -1
git diff --name-only origin/main...HEAD
rg -n "class .*Schema|dataclass|TypedDict|BaseModel|SessionSummary|SessionState|collection|document|to_dict|from_dict" backend/firestore backend/live_agent backend/session_utils.py
rg -n "def .*\\(|class .*\\(|async def .*\\(" backend/main.py backend/live_agent backend/routines evals test
rg -n "Phase 1|Langfuse|LangSmith|ADK|Firestore|No video storage|Frontend stays dependency-free|Evals" specs docs README.md
```

Expected result:

- The files changed by the PR align with files the agent inspected.
- Schema-affecting changes are reviewed against `backend/firestore/schema.py`.
- Interface-affecting changes are reviewed against the defining module, not only the call site.
- Spec-sensitive changes are reviewed against the Phase 1 spec and roadmap.

## Phase 2: Architectural Boundary & State Drift Analysis

Agents can make an early correct change and later break it during a long multi-file session. Review every touched file as a coordinated change, not as independent hunks.

### Structural Drift Commands

```bash
git diff-tree --no-commit-id --name-only -r HEAD
git diff --name-only origin/main...HEAD
git diff --check origin/main...HEAD
rg -n "from backend\\.|import backend\\.|SessionManager|SessionState|SessionSummary|extract_end_summary|append_event|complete_session" $(git diff --name-only origin/main...HEAD | rg "^(backend|evals|test)/" || true)
```

Expected result:

- Modified files are internally consistent across imports, types, and session contracts.
- No change bypasses the owning module for session state, routine planning, tracing, or summary extraction.
- No helper intended to remain internal is exposed through API handlers or persisted payloads without an explicit adapter.

### Critical Boundary Audit Targets

| Boundary Risk | Detection Vector | Action If Detected |
| --- | --- | --- |
| Leaked internals | Internal session or Firestore models exposed directly to browser-facing messages without a DTO or serialized payload boundary. | Require explicit response payload shaping in the API/WebSocket handler. |
| Race conditions | Shared session state updated across async WebSocket tasks without using the existing `SessionManager` lifecycle methods. | Reject PR; require a single state mutation path or explicit synchronization. |
| Stale constants | Hardcoded thresholds, model names, trace names, or URLs introduced instead of existing config/env/spec constants. | Centralize to config, environment, or documented constants. |
| Trace flooding | Per-frame, per-audio-chunk, or per-WebSocket-message spans. | Replace with logs/metrics or application-layer spans only. |
| Eval theater | Eval cases that only assert success paths or mirror implementation details. | Require trace-derived failure cases and known-bad examples. |

## Exact Grep Commands

Run every command from the repository root. For commands marked `must return no matches`, any match is a review finding unless the PR explains why it is acceptable.

### 1. Direct Gemini REST Calls

All AI calls must go through ADK. Direct Gemini REST calls are forbidden.

```bash
rg -n "generativelanguage|v1beta/models|https://.*gemini|requests\.(get|post|put|patch)|httpx\.(get|post|put|patch)|aiohttp|urllib\.request" backend evals test scripts
```

Expected result:

- No direct Gemini REST endpoint usage.
- `httpx` is allowed only for Langfuse REST trace queries in `test/trace_harness.py`.

### 2. LangSmith Drift

The implemented platform is Langfuse. New code must not reintroduce LangSmith dependencies, imports, or env vars.

```bash
rg -n "langsmith|LANGSMITH|traceable" backend evals test scripts .github pyproject.toml backend/requirements.txt specs README.md
```

Expected result:

- No new runtime code depends on LangSmith.
- Existing historical spec references are acceptable only in docs that clearly explain the decision history.

### 3. Langfuse Coverage

The PR must include eval and trace integration points for the observed Phase 1 failure patterns.

```bash
rg -n "Langfuse|langfuse|observe|score|session_summary_generation|routine_plan|interruption|exercise_update|gemini_live_coach_turn|propagate_attributes" backend evals test scripts .github
```

Expected result:

- Session setup / routine planning traces are present.
- Gemini coach turn traces are present.
- Exercise update traces are present.
- Pause/resume traces are present.
- Session summary generation traces are present.
- Eval scores can be posted to Langfuse when credentials exist, but local evals must still run without credentials.

### 4. High-Frequency Trace Regression

Do not trace every WebSocket receive, audio chunk, or video frame. Those belong in logs or metrics.

```bash
rg -n "@observe|@traceable|Langfuse|langfuse|trace" backend/main.py backend/live_agent backend/routines test/trace_harness.py
```

Expected result:

- Tracing is on application-layer operations.
- There is no per-frame, per-audio-chunk, or per-WebSocket-message tracing loop.
- Any tracing inside a loop must be for low-frequency semantic events such as exercise updates or session summaries.

### 5. Video Storage Prohibition

User video must be processed in real time and discarded. This command must return no matches that persist frame/image data.

```bash
rg -n "video.*(save|store|persist|write|upload)|frame.*(save|store|persist|write|upload)|image.*(save|store|persist|write|upload)|base64.*(save|store|persist|write|upload)|blob.*(save|store|persist|write|upload)" backend evals test scripts
```

Expected result:

- No persisted raw video, frames, image blobs, or base64 frame payloads.
- Test fixtures may include a minimal fake frame only when it is not written to durable storage.

### 6. Secrets and Credentials

Secrets must be injected by environment variables and GitHub Actions secrets, never committed.

```bash
rg -n "AIza|sk-|LANGFUSE_SECRET_KEY=.*[A-Za-z0-9_-]{12,}|GOOGLE_API_KEY=.*[A-Za-z0-9_-]{12,}|PRIVATE KEY|BEGIN .*PRIVATE KEY|password\s*=|secret\s*=" . --glob '!uv.lock'
```

Expected result:

- No committed API keys, private keys, or literal secret values.
- GitHub Actions references such as `${{ secrets.LANGFUSE_SECRET_KEY }}` are acceptable.

### 7. Frontend Dependency Boundary

The frontend must remain vanilla HTML/CSS/JS unless the PR explicitly changes the tech stack spec.

```bash
rg -n "package\.json|vite|webpack|react|vue|svelte|angular|npm install|yarn|pnpm|node_modules|import .* from ['\"](react|vue|svelte)" .
```

Expected result:

- No frontend framework or JS build system is added.
- Existing browser-native imports and static files under `backend/static/**` are acceptable.

### 8. Eval Dataset Provenance

Evals must target trace-observed failures, not imagined gaps.

```bash
rg -n "failures_observed|failure_pattern|trace|observed|expected_pass|session_summary_cases|setup_latency_cases|coach_premature_corrections" evals specs README.md
```

Expected result:

- `evals/dataset.json` names observed failure patterns.
- Each negative eval case has a `failure_pattern`.
- The PR description or spec update ties the dataset to Group 3 trace findings.

### 9. CI Evals Trigger

CI must run evals on pull requests that touch agent logic.

```bash
rg -n "evals:|python -m evals\.run_evals --ci|pull_request|needs: \[test\]|LANGFUSE_SECRET_KEY|LANGFUSE_PUBLIC_KEY" .github/workflows/ci.yml
```

Expected result:

- The eval job runs on PRs.
- The eval job depends on tests.
- Langfuse credentials are optional for local scoring but wired for CI score posting.

### 10. Session End and Summary Contract

The session summary is part of the user-facing trust contract. Confirm end events still produce complete summaries.

```bash
rg -n "type.*end|session_state.*ended|extract_end_summary|SessionSummary|session_summary_generation|rep_count|exercise_type|form_corrections|session_goal" backend evals test
```

Expected result:

- `end` messages preserve `exercise_type`, `rep_count`, `form_corrections`, and `session_goal`.
- Summary extraction handles both top-level fields and nested `summary` payloads.
- The eval suite includes missing/zero summary regressions.

### 11. Mock Proliferation and Test Fidelity

Agent-generated tests must not pass by mocking away the behavior under review.

```bash
rg -n "unittest\\.mock|patch\\(|MagicMock|Mock\\(|monkeypatch|pytest\\.fixture|responses|respx|mocker|AsyncMock" $(git diff --name-only origin/main...HEAD | rg "^(test|evals)/" || true)
```

Expected result:

- Mocks do not replace the exact function or service layer under test.
- Integration-style tests use real local code paths where possible.
- External services such as Firestore, Gemini, and Langfuse may be disabled or faked only at the boundary.

### 12. Error and Boundary Path Coverage

The test suite must cover error paths, not only successful sessions.

```bash
rg -n "pytest\\.raises|with pytest\\.raises|assert .*error|assert .*fail|expected_pass.*false|wantErr|Exception|ValueError|KeyError|status_code.*(4|5)|409|422|timeout|missing|null|zero" test evals
```

Expected result:

- Evals include negative cases with `expected_pass: false`.
- Session summary tests include missing, null, or zero-value regressions.
- WebSocket/session lifecycle tests include interruption, timeout, or premature-content checks when those paths are touched.

### 13. Success-Only Test Smell

Use this command when new tests are added. If the PR adds tests and this command has no meaningful matches, request stronger coverage.

```bash
rg -n "expected_pass.*false|pytest\\.raises|assert .*not|assert .*== 0|assert .*is None|assert .*False|timeout|missing|null|error|fail|invalid|interruption|pause|resume" $(git diff --name-only origin/main...HEAD | rg "^(test|evals)/" || true)
```

Expected result:

- New tests include at least one failure, boundary, or recovery path when behavior has branches.
- Positive-only tests are acceptable only for narrow documentation or smoke-test changes.

## Architectural Boundaries

Reviewers must block the PR if it violates any of these boundaries.

1. **ADK owns AI runtime access.** Backend code may configure and observe Gemini Live through ADK, but it must not call Gemini REST endpoints directly.
2. **Langfuse is the Phase 1 observability platform.** LangSmith references in old specs are historical only; new runtime code must use Langfuse.
3. **Trace semantic events, not raw transport.** Application-layer spans include session setup, coach turns, exercise updates, interruption handling, and summary generation. Raw audio chunks, video frames, and every inbound WebSocket message must not become individual traces.
4. **No raw video persistence.** The app may send frame metadata and transient frame payloads to the live model, but it must not store, upload, or train on user video.
5. **Frontend remains dependency-free.** `backend/static/**` stays browser-native HTML/CSS/JS. Do not add React, Vite, Webpack, npm, or a package manifest without a tech-stack spec update.
6. **Firestore stores session metadata only.** Valid persisted data includes session ids, timestamps, pause counts, exercise focus, rep counts, corrections, goals, and summary fields.
7. **Evals follow traces.** New evaluators must correspond to observed trace failure patterns and include passing and failing examples.
8. **CI remains deterministic without external services.** Tests and evals must pass locally without Firestore, Gemini, or Langfuse credentials. Posting Langfuse scores may be best-effort.
9. **Pause/resume is first-class.** Changes must preserve interruption events, pause duration, recovery state, and summary continuity.
10. **Latency guardrails stay intact.** Frame timestamps, stale-frame rejection, RTT echoing, adaptive frame rate, and user-visible latency degradation must not regress.

## Required Verification Steps

Run these commands before approving. Paste the command results into the review.

### Static Review

```bash
ruff check backend/ test/ evals/
uv run --python 3.11 python -m py_compile backend/main.py backend/session_utils.py backend/live_agent/session_manager.py evals/evaluators.py evals/run_evals.py test/trace_harness.py
```

### Unit and Integration Tests

```bash
PYTHONPATH=. ENABLE_FIRESTORE=false GOOGLE_GENAI_USE_VERTEXAI=false GOOGLE_CLOUD_PROJECT=chaos-fit uv run --python 3.11 python -m pytest test/ --ignore=test/test_firestore_write.py -v
```

### Eval Verification

```bash
PYTHONPATH=. ENABLE_FIRESTORE=false GOOGLE_GENAI_USE_VERTEXAI=false GOOGLE_CLOUD_PROJECT=chaos-fit uv run --python 3.11 python -m evals.run_evals --ci
```

Expected result:

- All expected-pass cases pass.
- All known-bad cases fail in the intended way.
- The command exits `0` because evaluator behavior matches `expected_pass`.

### Manual Trace Harness

Run this only when the PR changes WebSocket session flow, trace instrumentation, summary extraction, pause/resume, or coach readiness.

Terminal 1:

```bash
uv run --python 3.11 python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

Terminal 2:

```bash
PYTHONPATH=. CHAOSFIT_WS_URL=ws://localhost:8080 uv run --python 3.11 python test/trace_harness.py --scenario clean_session --runs 3
PYTHONPATH=. CHAOSFIT_WS_URL=ws://localhost:8080 uv run --python 3.11 python test/trace_harness.py --scenario session_with_interruption --runs 3
PYTHONPATH=. CHAOSFIT_WS_URL=ws://localhost:8080 uv run --python 3.11 python test/trace_harness.py --scenario misidentified_exercise --runs 3
```

Expected result:

- Each run receives `session_state:active` before model content.
- Each run receives `session_state:ended`.
- Summaries include non-null `exercise_type` and positive `rep_count` when exercise activity was sent.
- Langfuse summary checks pass when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are configured; otherwise the harness may skip remote Langfuse checks but must still pass local WebSocket assertions.

### CI Verification

For a PR, confirm the GitHub Actions checks show:

- `lint` passed.
- `test` passed.
- `evals` passed.
- No deployment job ran on the PR.

For a merge to `main`, confirm:

- Build and push completed.
- Cloud Run deploy completed.
- `/healthz` returns `{"status":"healthy"}` after deploy.

## Review Findings Format

Lead with concrete findings. Each finding must include:

- File and line number.
- The violated boundary or grep command.
- The behavioral risk.
- The exact verification step that would catch or prove the fix.

Do not approve the PR until all blocking findings are fixed or explicitly accepted by the owner.
