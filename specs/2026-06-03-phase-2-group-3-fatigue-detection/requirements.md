# Requirements: Phase 2 Group 3 — Fatigue Signal Detection

## Goal
Give the coach a native path to report observed fatigue so adaptive scheduling has a real signal to act on, not just a default.

## In scope

1. `report_fatigue` ADK tool — schema `{fatigue_level: float (0–1), confidence: str, observed_cues: list[str]}`; registered alongside `emit_exercise_data` in the coach agent
2. Tool response routed in `main.py._process_coach_tool_event` to `session_manager.append_event("fatigue_update", payload)`
3. `append_event` handling for `fatigue_update` — reads `fatigue_level` into `state.recent_fatigue`; fires `@observe(name="fatigue_update")` Langfuse span
4. `coach-system-instruction` prompt updated with specific observable cues and when to call `report_fatigue`

## Out of scope / deferred

- Rolling fatigue history window — Group 4 uses the scalar `recent_fatigue`; a history window is Phase 4 territory
- Fatigue-triggered rescheduling — Group 4 owns `compute_difficulty_modifier`; Group 3 only supplies the signal
- CI eval for fatigue detection quality — deferred until real traces accumulate post-merge

## Decisions & constraints

**Same FunctionTool pattern as `emit_exercise_data`.** `report_fatigue` is a plain Python function in `backend/coach_agent/response_handler.py` wrapped with `FunctionTool`, registered in `agent.py` alongside the existing tool, and routed in `main.py._process_coach_tool_event` by checking `response.get("type") == "fatigue_update"`.

**`append_event` is the authority for state updates.** Do not set `state.recent_fatigue` directly in `main.py`; route through `append_event("fatigue_update", ...)` so the event is written to Firestore and the Langfuse trace fires in one place.

**`fatigue_level` not `fatigue` in the payload.** Existing `append_event` reads the key `"fatigue"` for legacy events. The new `fatigue_update` path reads `"fatigue_level"` explicitly to avoid ambiguity.

**Prompt update goes to Langfuse only.** Run `scripts/upload_prompts.py` after merge to push the updated `coach-system-instruction`; no code redeploy needed.

## Background

`SessionState.recent_fatigue` exists but is currently only updated when an external caller passes `{"fatigue": ...}` in a generic event payload — there is no coach-initiated path. Group 2 rescheduling already reads `recent_fatigue` via `AdaptiveContext`; Group 4 difficulty adjustment will read it too. Group 3 closes the gap by giving the coach a structured tool call to emit the signal during a live session.
