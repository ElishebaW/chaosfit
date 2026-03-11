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
    + "\n\n"
    + "IMPORTANT: When you provide exercise corrections, rep counts, or exercise instructions, "
    "use the emit_exercise_data tool to ensure proper tracking. "
    "CRITICAL: Always include the current session_id when calling emit_exercise_data. "
    "The session_id is available in the conversation context or you can infer it from the WebSocket connection. "
    "Example: emit_exercise_data(text='Do 10 squats', session_id='demo-session-123'). "
    "This ensures all exercise data is captured for session summaries.",
    tools=[emit_exercise_data_tool],
)
