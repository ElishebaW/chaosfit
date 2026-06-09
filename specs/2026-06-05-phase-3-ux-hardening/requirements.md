# Requirements: Phase 3 — UX Hardening

## Goal
A user opens ChaosFit, tells the coach what they have (5 minutes, a corner of their kitchen), and gets a safe, effective, personalized workout — with real-time form guidance — without needing a gym, equipment, or a scheduled appointment.

## In scope
- Pause/resume with full state recovery (no dropped reps, no lost session context)
- Guided pre-session setup flow (goal, duration, space, energy level — before streaming starts)
- Improved visual feedback overlays (form cues on canvas, not just voice)
- Clearer session summary UI (not just JSON, a readable post-workout card)

## Out of scope / deferred
- Nothing deferred — all four Phase 3 items are in scope

## Decisions & constraints
- **No new frontend dependencies** — Canvas API for overlays, Vanilla JS for setup flow and summary card; stays dependency-free per tech-stack constraint
- **Setup flow requires no login** — pre-session inputs (goal, duration, space, energy) are session-scoped only; no user profile or auth required
- **Summary data from Firestore** — the post-workout card reads from the existing `session_summaries` Firestore collection; no new storage schema unless fields are missing
- **Overlays are client-side only** — form cues rendered on the Canvas API without a server round-trip; no video stored

## Background
Phase 3 closes the first-time user gap. Phases 0–2 built a stable, intelligent coaching session. Phase 3 makes it usable without onboarding: a user who lands on the app cold should be guided into a session, coached with visual + audio feedback, and land on a readable summary — without reading docs or asking what to do next.
