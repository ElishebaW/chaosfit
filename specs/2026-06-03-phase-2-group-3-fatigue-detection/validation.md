# Validation: Phase 2 Group 3 — Fatigue Signal Detection

## Done when

`report_fatigue` tool is callable by the coach and its payload reaches `state.recent_fatigue` correctly in tests. After a real session, Langfuse shows a `fatigue_update` span with `fatigue_level` and `observed_cues`.

## Checklist

- [ ] `report_fatigue(fatigue_level=0.8, confidence="high", observed_cues=["labored breathing"])` returns `{"status": "success", "type": "fatigue_update", "fatigue_level": 0.8, ...}`
- [ ] `fatigue_level` is clamped: values < 0.0 become 0.0, values > 1.0 become 1.0
- [ ] `report_fatigue_tool` is registered in `agent.py` and visible in `agent.tools`
- [ ] `append_event("fatigue_update", {"fatigue_level": 0.7, ...})` sets `state.recent_fatigue == 0.7`
- [ ] `append_event` with `fatigue_update` does not update `state.rep_count` or `state.form_corrections`
- [ ] Langfuse smoke test: run a real session, trigger a fatigue cue (slouch, slow down), confirm a `fatigue_update` span appears in the Langfuse Sessions view with `fatigue_level` and `observed_cues` populated

## How to verify

**Unit tests** (`test/test_fatigue_detection.py`): test the tool function directly (clamping, return schema), and test `append_event("fatigue_update", ...)` state updates.

**Langfuse smoke test**: after deploying, start a session and deliberately show signs of fatigue. Open Langfuse → Sessions → find the session → confirm a `fatigue_update` span is present with `fatigue_level` and `observed_cues`.

**CI**: existing test suite stays green; new tests added in this group must pass.
