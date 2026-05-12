# Phase 0 — Foundation: Requirements

## Goal

Make the deployed app stable and measurable before building on top of it. Phase 1 (AI Quality / LangSmith tracing) cannot be meaningfully executed until this foundation is solid.

## Scope

All three workstreams of Phase 0:
- CI/CD Pipeline
- Cloud Run Bug Fixes
- Audio/Video Sync & Coaching Latency

## Decisions & Context

### CI/CD Pipeline

- GitHub Actions is the CI/CD system; Artifact Registry is the container registry; Cloud Run is the deployment target (see tech-stack.md)
- Single Cloud Run service — no staging environment exists yet; CI deploys directly to the live service on every push to `main`
- Secrets must not appear in `.env` files committed to CI — all secrets injected via GitHub Actions secrets as Cloud Run env vars
- Branch protection on `main` must block merges when any CI job fails

### Cloud Run Bug Fixes

- The app is already deployed; this workstream fixes known instability, not a new deployment
- `min-instances: 1` on production is a deliberate tradeoff: accepts a small always-on cost to guarantee no cold-start failures during live demos

### Audio/Video Sync & Coaching Latency

- Root cause: the coaching agent receives frames 1–2+ seconds stale, so form corrections refer to movements the user has already completed
- Three root causes, addressed in order: (1) frames lack a capture timestamp, (2) stale frames are not rejected, (3) there is no RTT measurement
- The 3-second stale frame threshold is the starting value; may be tuned once RTT telemetry produces real-world data
- Buffered audio playback closes the perceptual gap: corrections land aligned with the movement that triggered them rather than 1–2s later

## Out of Scope

- LangSmith tracing (Phase 1)
- Coaching logic or prompt changes
- New exercises or expanded exercise library
- UI feature changes beyond the latency degradation indicator
- Storing user video data (remains prohibited by mission.md)
