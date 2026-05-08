# ChaosFit — Tech Stack

This document describes the current, locked technology choices for ChaosFit. Changes to this stack require an explicit decision and update here.

## Backend

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | ADK and Gemini SDK are Python-native |
| Web framework | FastAPI | Async WebSocket support, minimal overhead |
| AI runtime | Google ADK (Application Development Kit) | Manages Gemini Live API session lifecycle |
| AI model | Gemini Live API (`gemini-2.5-flash-native-audio-preview`) | Native multimodal audio + video, real-time streaming |
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
| Agent tracing | LangSmith | Trace ADK/Gemini calls, build eval datasets, run regressions in CI |
| Latency telemetry | Client-side RTT (WebSocket) | Measure frame-to-coaching round-trip; surface degradation to user |

## Constraints & Guardrails

- **No video storage** — frames are processed in real time and discarded. No user video is persisted.
- **No external ML services** for form analysis beyond Gemini multimodal — keeps the stack minimal.
- **Frontend stays dependency-free** until there is a clear reason to add a framework. Vanilla JS is intentional.
- **All AI calls go through ADK** — do not call the Gemini REST API directly from the backend.
