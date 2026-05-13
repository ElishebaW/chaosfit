# ChaosFit — Roadmap

Phases are ordered by what delivers the most mission-critical value first. Each phase is small enough to ship independently.

---

## Phase 0 — Foundation (do first, unblocks everything)

*Goal: make the deployed app stable and measurable before building on top of it.*

### CI/CD Pipeline
- [x] GitHub Actions workflow: lint → test → build Docker image → push to Artifact Registry → deploy to Cloud Run
- [x] Block merges to `main` on failing tests or build errors
- [x] Separate staging and production Cloud Run services (deploy to staging first)
- [x] Secrets managed via GitHub Actions secrets → Cloud Run env vars (no `.env` in CI)

### Cloud Run Bug Fixes
- [x] Audit and fix current deployment failures (cold start timeouts, missing env vars, health check misconfiguration)
- [x] Confirm `/healthz` returns `{"status": "healthy"}` reliably after deploy
- [x] Set minimum instances to 1 to eliminate cold-start latency for live demos

### Audio/Video Sync & Coaching Latency
The coaching agent's audio corrections are responding to frames that may be 1–2+ seconds stale. Three root causes to fix in order:

- [x] **Stamp frames** — add `capturedAt: Date.now()` to every video payload in `app.js:1562`
- [x] **Stale frame rejection** — server skips frames older than 3s (`main.py:273–415`); logs a warning
- [x] **RTT telemetry** — client records `sentAt` per message; server echoes it back; client computes and logs round-trip time
- [x] **Adaptive frame rate** — drop from 1 FPS to 0.5 FPS when RTT exceeds 2s; recover automatically
- [x] **Buffered audio playback** — delay audio in `pcm-player-processor.js` by rolling average RTT so corrections align with the movement that triggered them
- [x] **User-visible degradation indicator** — surface a warning in the UI if coaching latency exceeds a configurable threshold (default: 3s)

**Done when:** A coaching correction of "keep your chest up" reliably refers to what the user is doing right now, and the app reports its own latency health.

---

## Phase 1 — AI Quality

*Goal: make the AI coach more accurate and trustworthy during a session, and give us the tooling to measure it.*

### Agent Observability — LangSmith Tracing

**Decision:** Add traces to every workflow element first. Observed trace data will drive what evals get written — not assumptions.

Trace each step independently so timing, inputs, and failures are visible per component:

- [ ] **WebSocket message receipt** — trace each inbound message: type, size, timestamp
- [ ] **Video frame pipeline** — trace frame capture → encode → send; include `capturedAt`, frame age by the time it's processed server-side
- [ ] **Session setup / routine planner** — trace inputs (duration, equipment, level) → generated routine plan; log which exercise blocks were selected
- [ ] **Gemini Live API call (ADK)** — trace every coach turn: prompt context sent, response received, tokens, latency
- [ ] **Exercise detection / rep counting** — trace detected exercise type, confidence, rep delta per frame
- [ ] **Interruption handling** — trace pause/resume events: session state before and after, time paused, context recovered
- [ ] **Session summary generation** — trace final aggregation: reps, corrections, duration, any dropped state

Once traces are collected from real sessions, use them to identify where the agent drifts, fails, or is slow — then define evals from that evidence.

- [ ] Define eval dataset from trace-observed failures (not pre-assumed)
- [ ] Write evaluators targeting the specific gaps traces reveal
- [ ] Run evals in CI on PRs touching agent logic

### Coaching Accuracy
- [ ] Improve exercise detection accuracy (reduce false positives in rep counting)
- [ ] More precise, concise form feedback (timing and specificity of corrections)
- [ ] Advanced pose estimation for common bodyweight movements (squat, push-up, plank)
- [ ] Expand exercise library beyond current 20+ movements

**Done when:** LangSmith evals are running in CI and rep counting is reliable enough that a user trusts the summary numbers.

---

## Phase 2 — Adaptive Intelligence

*Goal: make the session smarter mid-workout, not just at setup.*

- [ ] Mid-session adaptive scheduling (restructure remaining blocks based on elapsed time and interruptions)
- [ ] Fatigue signal detection from video/audio cues
- [ ] Dynamic difficulty adjustment within a session
- [ ] Smarter interruption recovery (coach picks up contextually, not from the top)

**Done when:** A session interrupted twice still delivers a complete, sensible workout.

---

## Phase 3 — UX Hardening

*Goal: make the user experience smooth enough for daily use.*

- [ ] Pause/resume with full state recovery (no dropped reps, no lost session context)
- [ ] Guided pre-session setup flow (goal, duration, space, energy level — before streaming starts)
- [ ] Improved visual feedback overlays (form cues on canvas, not just voice)
- [ ] Clearer session summary UI (not just JSON, a readable post-workout card)

**Done when:** A first-time user can complete a session start-to-summary without reading docs.

---

## Phase 4 — Platform

*Goal: extend ChaosFit beyond the browser session.*

- [ ] Multi-session progress tracking (history, trends, streak)
- [ ] Progressive workout programs spanning multiple sessions
- [ ] Mobile app (PWA first, React Native if needed)
- [ ] Social / community features (optional accountability layer)
- [ ] Wearable integration (heart rate, intensity from Apple Watch / Garmin)

**Done when:** A user can look back at 30 days of workouts and see a coherent fitness arc.

---

## Phase 5 — App Rename

*Goal: replace "ChaosFit" with the new name everywhere — codebase and GCP infrastructure.*

### Code & Display Strings
- [ ] Decide on the new name
- [ ] Update display strings: page title, `<title>` tag, UI copy, coaching messages
- [ ] Update `APP_NAME` constant in `backend/main.py`
- [ ] Update `pyproject.toml` project name and any references in `README.md` / docs
- [ ] Update GitHub repo name and description (Settings → rename)
- [ ] Update `chaosfit.app` domain / Vercel project display name if applicable
- [ ] Search codebase for any remaining hardcoded "ChaosFit" / "chaosfit" strings and replace

### GCP Infrastructure Rebuild (new project ID to match new name)
- [ ] Create new GCP project with a name-matched project ID
- [ ] Enable required APIs: Cloud Run, Artifact Registry, Firestore, IAM
- [ ] Create Artifact Registry repository in the new project
- [ ] Create Cloud Run service in the new project
- [ ] Set up Workload Identity Federation: new pool, provider, service account, IAM bindings
- [ ] Update GitHub Actions secrets: `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GOOGLE_API_KEY`
- [ ] Update all project ID references in `ci.yml` (`PROJECT_ID`, `REPOSITORY`, `SERVICE`, image path)
- [ ] Trigger a CI deploy to the new project and confirm `/healthz` passes
- [ ] Delete the old `chaos-fit` GCP project once new project is confirmed working

**Done when:** The app is live under the new name on a new GCP project, and the old `chaos-fit` project is deleted.

---

## What's Out of Scope (for now)

- Nutrition tracking or dietary coaching
- Synchronous human-trainer features (live video calls)
- Gym equipment workouts — bodyweight-only remains the constraint
- Storing or processing user video beyond the current session
