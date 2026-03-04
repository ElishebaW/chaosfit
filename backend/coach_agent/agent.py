"""ADK agent configuration for ChaosFit live workout coaching."""

from __future__ import annotations

import os

from google.adk.agents import Agent


agent = Agent(
    name="chaosfit_live_coach",
    model=os.getenv("DEMO_AGENT_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"),
    instruction=(
        "You are a live fitness coach for parents. "
        "Give short, safe, corrective cues during exercise. "
        "If form looks risky, interrupt immediately with a concise correction. "
        "Prioritize safety, breathing, posture, and joint alignment."
    ),
)
