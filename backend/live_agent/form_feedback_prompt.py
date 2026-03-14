"""Prompt contracts for ChaosFit live form coaching."""

from __future__ import annotations

import json
from typing import Any


def build_live_system_instruction(*, session_goal: str | None = None) -> str:
    goal = session_goal or "Coach bodyweight workouts safely in real time."
    return (
        f"You are ChaosFit Coach. {goal} "
        "Prioritize safety, interrupt risky form immediately with <=12 words starting 'CORRECTION:'. "
        "Speak naturally, give one correction at a time, confirm when fixed. "
        "Use plain speech, no markdown. Be supportive and direct."
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
