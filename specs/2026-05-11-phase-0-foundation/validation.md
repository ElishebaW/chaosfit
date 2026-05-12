# Phase 0 — Foundation: Validation Checklist

This phase is mergeable when all four sections below are checked.

## 1. CI Green

- [ ] GitHub Actions workflow runs on every PR to `main`
- [ ] All jobs pass: lint, test, Docker build, push to Artifact Registry, deploy to Cloud Run
- [ ] A PR with a failing test is blocked from merging (branch protection enforced)
- [ ] No secrets appear in `.env` files or workflow YAML — all injected via GitHub Actions secrets

## 2. Health Check Passes

- [ ] `GET /healthz` returns `{"status": "healthy"}` after a fresh CI-triggered deploy
- [ ] Health check passes within Cloud Run's configured timeout (no cold-start failures)
- [ ] Service has `min-instances: 1` confirmed in Cloud Run config

## 3. Live Session Smoke Test

- [ ] A full coaching session runs start-to-finish without drops or disconnects
- [ ] Audio corrections are audibly aligned with the movement they refer to (no perceptible lag)
- [ ] UI shows a latency warning when coaching delay exceeds 3s (trigger deliberately to verify)
- [ ] Interrupting and resuming the session does not break the audio/video stream

## 4. Observability Data in Hand

- [ ] Client-side RTT logs visible in browser console during a session (`sentAt` → echo → RTT computation confirmed)
- [ ] Server logs show stale-frame rejection warnings when a frame older than 3s arrives
- [ ] RTT data from at least one real session captured and reviewed — confirms adaptive frame rate triggers at the correct threshold

## Definition of Done

All four sections are fully checked. A reviewer can run the CI pipeline, hit the health endpoint, complete a live session, and inspect RTT logs — without any additional setup or manual workarounds.
