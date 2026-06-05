# ChaosFit — Tech Stack

This document describes the current, locked technology choices for ChaosFit. Changes to this stack require an explicit decision and update here.

## Backend

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | ADK and Gemini SDK are Python-native |
| Web framework | FastAPI | Async WebSocket support, minimal overhead |
| AI runtime | Google ADK (Application Development Kit) | Manages Gemini Live API session lifecycle |
| AI model — live coach | Gemini Live API (`gemini-2.5-flash-live-001`) | Native multimodal audio + video, real-time streaming |
| AI model — block planner | `gemini-2.5-flash` (env: `NEXT_BLOCK_MODEL`) | Generates the next workout block as structured JSON |
| AI model — session summary | `gemini-2.5-flash` (env: `SUMMARY_MODEL`) | Produces the post-session summary from trace data |
| Package manager | uv | Fast dependency resolution, lockfile support |
| ASGI server | Uvicorn | Production-grade, pairs with FastAPI |

## Database

| Component | Choice | Why |
|-----------|--------|-----|
| Session storage | Google Cloud Firestore | Serverless NoSQL, fits session-document shape, GCP-native |

## Frontend

| Component | Choice | Why |
|-----------|--------|-----|
| UI layer | HTML5 / CSS3 / Vanilla JS | Zero build tooling, ships directly from FastAPI static |
| Realtime transport | WebSocket API | Bidirectional streaming with backend |
| Media capture | WebRTC (getUserMedia) | Browser-native camera + microphone access |
| Visual feedback | Canvas API | Client-side motion/form overlays, no server round-trip |

## Infrastructure

| Component | Choice | Why |
|-----------|--------|-----|
| Hosting | Google Cloud Run | Serverless containers, scales to zero, GCP-native |
| Containerization | Docker | Reproducible builds, Cloud Run native format |
| CI/CD | GitHub Actions | lint → test → build → push to Artifact Registry → deploy to Cloud Run |

## Observability & Evals

| Component | Choice | Why |
|-----------|--------|-----|
| Agent tracing | Langfuse | Trace ADK/Gemini calls, build eval datasets, run regressions in CI |
| Latency telemetry | Client-side RTT (WebSocket) | Measure frame-to-coaching round-trip; surface degradation to user |
| Integration harness | `test/trace_harness.py` | Drives live WebSocket sessions and asserts Langfuse spans are produced; validates the observability pipeline that AI evals depend on |

### Two layers of quality tooling

These are distinct and both necessary:

**1. Trace harness (`test/trace_harness.py`) — pipeline integrity, not model quality**

Connects to a running server, drives scripted workout scenarios over WebSocket, and queries Langfuse to confirm the expected spans were written. It does *not* evaluate whether the coach said the right thing — it verifies that the instrumentation plumbing is working so that real session data actually reaches Langfuse. If the harness fails, AI evals will silently run on missing or corrupt data.

Current scenarios: `clean_session`, `session_with_interruption`, `misidentified_exercise`, `difficulty_adjustment`. Each targets a specific integration failure mode (e.g. `difficulty_adjustment` validates the full passive-inference pipeline: event → `_maybe_auto_adjust_difficulty` → `_apply_difficulty_adjustment` → Langfuse span).

**2. Langfuse evals in CI — model quality**

The AI quality harness: Langfuse eval datasets built from observed session traces are run in CI against any PR that touches agent logic. Evaluators check coaching accuracy (rep counting, form correction specificity, interruption handling). This is what improves model behavior — the trace harness just ensures the eval data pipeline is intact so these evals are trustworthy.

## Constraints & Guardrails

- **No video storage** — frames are processed in real time and discarded. No user video is persisted.
- **No external ML services** for form analysis beyond Gemini multimodal — keeps the stack minimal.
- **Frontend stays dependency-free** until there is a clear reason to add a framework. Vanilla JS is intentional.
- **All AI calls go through ADK** — do not call the Gemini REST API directly from the backend.
