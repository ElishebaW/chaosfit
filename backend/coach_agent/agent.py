"""ADK agent configuration for ChaosFit live workout coaching."""

from __future__ import annotations

import os

from google.adk.agents import Agent
from langfuse import get_client

from backend.live_agent.form_feedback_prompt import build_live_system_instruction
from backend.coach_agent.response_handler import emit_exercise_data_tool

_TOOL_SUFFIX = (
    "\n\nCRITICAL: ALWAYS call emit_exercise_data tool with session_id for ANY coaching feedback. "
    "Use for: form corrections, exercise instructions, rep counts, exercise types. "
    "Examples: emit_exercise_data(text='Keep your chest up', session_id='demo-session-123') "
    "or emit_exercise_data(text='Do 10 air_squats', session_id='demo-session-123'). "
    "Key exercises: air_squat, push_up, plank, reverse_lunge, mountain_climber, jumping_jack."
)

_GOAL = os.getenv(
    "COACH_SESSION_GOAL",
    "Coach in real time, interrupt risky form, and keep corrections short and actionable.",
)

coach_prompt = None
try:
    coach_prompt = get_client().get_prompt("coach-system-instruction", label="production")
    _instruction = coach_prompt.compile(goal=_GOAL)
except Exception:
    _instruction = build_live_system_instruction(session_goal=_GOAL) + _TOOL_SUFFIX

agent = Agent(
    name="chaosfit_live_coach",
    model=os.getenv("DEMO_AGENT_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"),
    instruction=_instruction,
    tools=[emit_exercise_data_tool],
)
