"""ADK agent configuration for ChaosFit live workout coaching."""

from __future__ import annotations

import os

from google.adk.agents import Agent

from backend.live_agent.form_feedback_prompt import build_live_system_instruction


agent = Agent(
    name="chaosfit_live_coach",
    model=os.getenv("DEMO_AGENT_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"),
    instruction=build_live_system_instruction(
        session_goal=os.getenv(
            "COACH_SESSION_GOAL",
            "Coach in real time, interrupt risky form, and keep corrections short and actionable.",
        )
    ),
)
