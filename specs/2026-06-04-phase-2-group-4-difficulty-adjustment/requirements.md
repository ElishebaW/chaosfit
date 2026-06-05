# Requirements: Phase 2 Group 4 — Dynamic Difficulty Adjustment

## Goal
Meet users where they are physically — adaptive, low-impact options that adjust in real time to the user's actual performance during a session.

## In scope
- Within-session difficulty adjustment: coach detects when the user is breezing through or visibly struggling and modifies upcoming block intensity
- Difficulty is expressed as rep-count and rest-interval changes only
- Agent can call an explicit ADK tool to trigger adjustment
- Passive inference: difficulty signal derived from rep pace and form quality observed via Gemini, not only from explicit fatigue reports

## Out of scope / deferred
- Exercise substitution (swapping push-up → knee push-up, etc.) — deferred; scope is reps + rest only
- Per-exercise difficulty presets or difficulty "levels" — adjustment is continuous, not stepped

## Decisions & constraints
- **No exercise substitution.** Difficulty = mutate `reps` and `rest_seconds` fields on remaining blocks. Do not change the exercise itself.
- **Compose with `report_fatigue`.** The fatigue tool from Group 3 is an upstream signal; difficulty adjustment consumes its output but also runs on independent pace/form signals.
- **ADK tool is the agent's handle.** The Gemini Live coach calls `adjust_difficulty` to record intent; the server applies the mutation to the session's pending blocks in Firestore.
- **Trace every adjustment.** Each adjustment event must appear as a Langfuse span (tool name, direction, delta values, trigger source) so we can audit agent behavior.

## Background
Groups 1–3 delivered interruption recovery, mid-session scheduling, and fatigue detection. Group 4 closes Phase 2 by letting the coach act on what it observes — not just report it. The Phase 2 acceptance bar is: *a session interrupted twice still delivers a complete, sensible workout.* Difficulty adjustment is the "sensible" part: a fatigued user should get a lighter next block, not the same one repeated.
