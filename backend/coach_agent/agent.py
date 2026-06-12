"""ADK agent configuration for ChaosFit live workout coaching."""

from __future__ import annotations

import os

from google.adk.agents import Agent
from langfuse import get_client

from backend.live_agent.form_feedback_prompt import build_live_system_instruction
from backend.coach_agent.response_handler import adjust_difficulty_tool, emit_exercise_data_tool, report_fatigue_tool

_TOOL_SUFFIX = (
    "\n\nCRITICAL: ALWAYS call emit_exercise_data tool with session_id for ANY coaching feedback. "
    "Use for: form corrections, exercise instructions, rep counts, exercise types. "
    "Examples: emit_exercise_data(text='Keep your chest up', session_id='demo-session-123') "
    "or emit_exercise_data(text='Do 10 air_squats', session_id='demo-session-123'). "
    "Key exercises: air_squat, push_up, plank, reverse_lunge, mountain_climber, jumping_jack.\n\n"
    "FATIGUE DETECTION: Call report_fatigue(fatigue_level, confidence, observed_cues, session_id) "
    "when you observe: labored breathing audible in the mic, 3+ form corrections in the last 2 minutes, "
    "visibly slowed pace, or form breakdown on consecutive reps. "
    "Set fatigue_level 0.3–0.5 for early signs, 0.6–0.8 for clear fatigue, 0.9–1.0 for near-failure.\n\n"
    "DIFFICULTY ADJUSTMENT: Call adjust_difficulty(direction, reason, session_id) to modify upcoming "
    "blocks when the user's effort level clearly mismatches the plan. "
    "Use direction='harder' when reps are completed well ahead of pace with no corrections and the user "
    "signals they want more challenge — wait until the end of a set, not mid-rep. "
    "Use direction='easier' when pace is slowing, form is breaking down, or the user explicitly asks to "
    "ease off. Do not call within 60 seconds of a previous adjust_difficulty call."
)

_GOAL = os.getenv(
    "COACH_SESSION_GOAL",
    "Coach in real time, interrupt risky form, and keep corrections short and actionable.",
)

coach_prompt = None
try:
    coach_prompt = get_client().get_prompt("coach-system-instruction", label="production")
    _instruction = coach_prompt.compile(goal=_GOAL) + _TOOL_SUFFIX
except Exception:
    _instruction = build_live_system_instruction(session_goal=_GOAL) + _TOOL_SUFFIX

agent = Agent(
    name="chaosfit_live_coach",
    model=os.getenv("DEMO_AGENT_MODEL", "gemini-live-2.5-flash-native-audio"),
    instruction=_instruction,
    tools=[emit_exercise_data_tool, report_fatigue_tool, adjust_difficulty_tool],
)
