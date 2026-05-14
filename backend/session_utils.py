"""Pure utility functions for parsing session payloads — no FastAPI or ADK dependencies."""

from __future__ import annotations

from typing import Any


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def normalize_corrections(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            entry = safe_str(item)
            if entry:
                out.append(entry)
        return out
    single = safe_str(value)
    return [single] if single else []


def extract_end_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary_block = payload.get("summary")
    if not isinstance(summary_block, dict):
        summary_block = {}
    exercise_type = safe_str(summary_block.get("exercise_type") or payload.get("exercise_type"))
    rep_count = safe_int(summary_block.get("rep_count") or payload.get("rep_count"))
    session_goal = safe_str(summary_block.get("session_goal") or payload.get("session_goal"))
    corrections = normalize_corrections(
        summary_block.get("form_corrections") or payload.get("form_corrections")
    )
    return {
        "exercise_type": exercise_type,
        "rep_count": rep_count,
        "session_goal": session_goal,
        "form_corrections": corrections,
    }
