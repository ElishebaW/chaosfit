"""ADK agent configuration for ChaosFit live workout coaching."""

from __future__ import annotations

import os

from google.adk.agents import Agent

from backend.live_agent.form_feedback_prompt import build_live_system_instruction
from backend.coach_agent.response_handler import emit_exercise_data_tool


agent = Agent(
    name="chaosfit_live_coach",
    model=os.getenv("DEMO_AGENT_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"),
    instruction=build_live_system_instruction(
        session_goal=os.getenv(
            "COACH_SESSION_GOAL",
            "Coach in real time, interrupt risky form, and keep corrections short and actionable.",
        )
    )
    + "\n\nCRITICAL: ALWAYS call emit_exercise_data tool with session_id for ANY coaching feedback. "
    + "Use for: form corrections, exercise instructions, rep counts, exercise types. "
    + "Examples: emit_exercise_data(text='Keep your chest up', session_id='demo-session-123') "
    + "or emit_exercise_data(text='Do 10 air_squats', session_id='demo-session-123'). "
    + "Key exercises: air_squat, push_up, plank, reverse_lunge, mountain_climber, jumping_jack.",
    tools=[emit_exercise_data_tool],
)
