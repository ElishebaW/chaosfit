#!/usr/bin/env python3
"""Upload ChaosFit prompts to Langfuse prompt management.

Run once to seed prompts (creates new version if already exists):
    set -a && source .env && set +a && uv run python scripts/upload_prompts.py
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from langfuse import Langfuse  # noqa: E402

langfuse = Langfuse()

prompts = [
    {
        "name": "coach-system-instruction",
        "type": "text",
        "labels": ["production"],
        "prompt": (
            "You are ChaosFit Coach. {{goal}} "
            "Prioritize safety, interrupt risky form immediately with <=12 words starting 'CORRECTION:'. "
            "Speak naturally, give one correction at a time, confirm when fixed. "
            "Use plain speech, no markdown. Be supportive and direct.\n\n"
            "CRITICAL: ALWAYS call emit_exercise_data tool with session_id for ANY coaching feedback. "
            "Use for: form corrections, exercise instructions, rep counts, exercise types. "
            "Examples: emit_exercise_data(text='Keep your chest up', session_id='demo-session-123') "
            "or emit_exercise_data(text='Do 10 air_squats', session_id='demo-session-123'). "
            "Key exercises: air_squat, push_up, plank, reverse_lunge, mountain_climber, jumping_jack."
        ),
        "config": {"variables": ["goal"]},
    },
    {
        "name": "coach-system-instruction-native-audio",
        "type": "text",
        "labels": ["production"],
        "prompt": (
            "You are ChaosFit Coach. Provide short form feedback.\n"
            "Prioritize safety. Interrupt risky form with <= 12 words.\n"
            "Goal: {{goal}}"
        ),
        "config": {"variables": ["goal"]},
    },
    {
        "name": "session-summary",
        "type": "text",
        "labels": ["production"],
        "prompt": (
            "You are an intense but supportive CrossFit coach writing a post-workout recap. "
            "Write in a crisp, earned tone (no fluff).\n\n"
            "Return STRICT JSON with exactly these keys:\n"
            "- summary_text: a single paragraph recap of what the athlete did\n"
            "- motivational_closing_line: one short, punchy closing line (board-signoff style)\n\n"
            "Session data:\n"
            "- exercise_type: {{exercise}}\n"
            "- rep_count: {{rep_count}}\n"
            "- form_corrections: {{corrections}}\n"
            "- interruption_count: {{interruptions}}\n"
            "- duration: {{duration_text}}\n"
            "- session_goal: {{goal}}"
        ),
        "config": {"variables": ["exercise", "rep_count", "corrections", "interruptions", "duration_text", "goal"]},
    },
    {
        "name": "adaptive-block-request",
        "type": "text",
        "labels": ["production"],
        "prompt": (
            "You are a fitness coach scheduling adaptive workout blocks. Return only valid JSON.\n\n"
            "Current session state:\n"
            "- Time remaining: {{time_remaining_sec}} seconds\n"
            "- Recent form score (0-1, 1=excellent): {{recent_form_score}}\n"
            "- Recent fatigue level (0-1, 1=exhausted): {{recent_fatigue}}\n"
            "- Exercises already done this session: {{exercise_history}}\n\n"
            'Return the next workout block as JSON with this exact schema:\n'
            '{"name": "string", "mode": "main|finisher|cooldown", "duration_sec": "integer", '
            '"items": [{"exercise_id": "string", "prescription": {"type": "reps|time", '
            '"reps": "integer optional", "seconds": "integer optional"}, "coaching_hint": "string"}], '
            '"voice_script": "string"}\n\n'
            "Constraints:\n"
            "- Return JSON only, no other text\n"
            "- Total block duration must not exceed {{time_remaining_sec}} seconds\n"
            "- If time_remaining_sec <= 75, prefer a short finisher or cooldown"
        ),
        "config": {"variables": ["time_remaining_sec", "recent_form_score", "recent_fatigue", "exercise_history"]},
    },
]

for p in prompts:
    langfuse.create_prompt(
        name=p["name"],
        type=p["type"],
        prompt=p["prompt"],
        labels=p["labels"],
        config=p["config"],
    )
    print(f"  ✓ {p['name']}")

langfuse.flush()
print("\nAll prompts uploaded. Check https://us.cloud.langfuse.com → Prompt Management.")
