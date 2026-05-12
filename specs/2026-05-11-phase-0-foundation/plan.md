# Phase 0 — Foundation: Implementation Plan

## Task Group 1 — CI/CD Pipeline

1. Create `.github/workflows/ci.yml` with jobs: lint → test → build Docker image → push to Artifact Registry → deploy to Cloud Run
2. Configure branch protection on `main`: require all CI jobs to pass before a PR can merge
3. Wire deployment: build and deploy to the single existing Cloud Run service on every push to `main`
4. Audit for hardcoded secrets or `.env` values; migrate everything to GitHub Actions secrets injected as Cloud Run env vars

## Task Group 2 — Cloud Run Bug Fixes

6. Audit current deployment: identify cold start timeouts, missing env vars, and health check misconfigurations
7. Fix `/healthz` endpoint so it reliably returns `{"status": "healthy"}` after a fresh deploy
8. Set `min-instances: 1` on the production Cloud Run service to eliminate cold-start latency for live demos
9. Verify health check passes end-to-end after a fresh CI-triggered deploy

## Task Group 3 — Audio/Video Sync & Coaching Latency

10. Stamp frames — add `capturedAt: Date.now()` to every video payload in `app.js` (around line 1562)
11. Stale frame rejection — server skips frames older than 3s (`main.py` lines 273–415); logs a warning per dropped frame
12. RTT telemetry — client records `sentAt` per message; server echoes it back; client computes and logs round-trip time
13. Adaptive frame rate — drop from 1 FPS to 0.5 FPS when RTT exceeds 2s; recover automatically when RTT falls back below threshold
14. Buffered audio playback — delay audio in `pcm-player-processor.js` by rolling average RTT so corrections align with the movement that triggered them
15. User-visible degradation indicator — surface a UI warning when coaching latency exceeds 3s (configurable threshold)
