# Validation: Phase 3 — UX Hardening

## Done when
A first-time user completes a session start-to-summary without reading docs or asking questions.

## Checklist
- [ ] Setup screen appears before streaming starts and collects goal, duration, space, and energy level
- [ ] Session goal entered in the setup flow is visible in the coach's instruction context (Langfuse trace shows it)
- [ ] After session ends, a readable post-workout card is displayed (not raw JSON)
- [ ] Summary card shows: exercise(s), total reps, duration, correction count, pause count
- [ ] Summary card renders correctly when Firestore is disabled (in-memory fallback)
- [ ] "Share / Copy" button copies a plain-text summary to clipboard
- [ ] Pause → page reload → resume preserves rep count, block index, and form corrections
- [ ] Reconnect path restores `SessionState` from Firestore if session exists but is not in memory
- [ ] Form-cue overlay appears on canvas after each exercise_update correction
- [ ] Overlay fades out after 3 seconds without obstructing the video feed
- [ ] `routine_plan_updated` events flash the upcoming block name on canvas
- [ ] No new frontend dependencies introduced (Canvas API + Vanilla JS only)

## How to verify
1. Open the app cold in an incognito window — confirm the setup screen appears and streaming only starts after submission.
2. Complete a short session (2–3 minutes), pause once mid-session, then resume — confirm no rep count or block loss in the summary.
3. Reload the page during a paused session and reconnect — confirm state is restored from Firestore.
4. Confirm the post-workout card renders without raw JSON visible anywhere.
5. Check Langfuse for the session trace — confirm `session_setup` span includes the goal from the setup form.
