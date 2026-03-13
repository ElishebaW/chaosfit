"""Prompt contracts for ChaosFit live form coaching."""

from __future__ import annotations

import json
from typing import Any


def build_live_system_instruction(*, session_goal: str | None = None) -> str:
    goal = session_goal or "Coach bodyweight workouts safely in real time."
    # Keep instruction short but include 10-second checking and exercise data tracking for native audio model
    return (
        "You are ChaosFit Coach. Provide short form feedback.\n"
        "Prioritize safety. Interrupt risky form with <= 12 words.\n"
        "Check form every 10 seconds and provide corrections if needed.\n"
        "IMPORTANT: When you provide exercise corrections, rep counts, or exercise instructions, use the emit_exercise_data tool to ensure proper tracking. CRITICAL: Always include the current session_id when calling emit_exercise_data. The session_id is available in the conversation context or you can infer it from the WebSocket connection. Example: emit_exercise_data(text='Do 10 squats', session_id='demo-session-123'). This ensures all exercise data is captured for session summaries.\n"
        "Add corrections to the form_corrections field when you identify form issue and say it to user. Check form every 10 seconds and provide corrections if needed - be proactive about form issues.\n"
        f"Goal: {goal}"
    )


def build_next_block_prompt(
    *,
    time_remaining_sec: int,
    recent_form_score: float | None,
    recent_fatigue: float | None,
    exercise_history: list[str],
) -> str:
    payload: dict[str, Any] = {
        "time_remaining_sec": time_remaining_sec,
        "recent_form_score": recent_form_score,
        "recent_fatigue": recent_fatigue,
        "exercise_history": exercise_history[-8:],
        "task": "Return the next adaptive workout block.",
        "schema": {
            "name": "string",
            "mode": "main|finisher|cooldown",
            "duration_sec": "integer",
            "items": [
                {
                    "exercise_id": "string",
                    "prescription": {
                        "type": "reps|time",
                        "reps": "integer optional",
                        "seconds": "integer optional",
                    },
                    "coaching_hint": "string",
                }
            ],
            "voice_script": "string",
        },
        "constraints": [
            "Return JSON only.",
            "Keep total block duration <= time_remaining_sec.",
            "If time_remaining_sec <= 75, prefer a short finisher/cooldown.",
        ],
    }
    return json.dumps(payload)
