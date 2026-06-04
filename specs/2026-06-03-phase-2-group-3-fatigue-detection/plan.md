# Plan: Phase 2 Group 3 — Fatigue Signal Detection

Each group is a shippable unit. Complete in order.

## Group 3 — Fatigue Signal Detection

1. Add `report_fatigue(fatigue_level, confidence, observed_cues, session_id)` function and `report_fatigue_tool = FunctionTool(report_fatigue)` to `backend/coach_agent/response_handler.py`. Return `{"status": "success", "type": "fatigue_update", "fatigue_level": <clamped 0–1>, "confidence": ..., "observed_cues": [...], "session_id": ...}`. Clamp `fatigue_level` to [0.0, 1.0].
2. Register `report_fatigue_tool` in `backend/coach_agent/agent.py` alongside `emit_exercise_data_tool`. Update `_process_coach_tool_event` in `backend/main.py` to route responses where `event_data.get("type") == "fatigue_update"` to `session_manager.append_event(session_id, "fatigue_update", payload)` instead of `"exercise_update"`.
3. In `backend/live_agent/session_manager.py`: add `@observe(name="fatigue_update")` trace function logging `session_id`, `fatigue_level`, `confidence`, `observed_cues`; add `fatigue_update` branch in `append_event` that reads `fatigue_level` into `state.recent_fatigue` and fires the trace.
4. In `scripts/upload_prompts.py`, append a `FATIGUE DETECTION` section to the `coach-system-instruction` prompt body specifying when to call `report_fatigue`: labored breathing audible in mic, 3+ form corrections in the last 2 minutes, visibly slowed pace, or form breakdown on consecutive reps. Run `upload_prompts.py` after merge to push the new version to Langfuse.
