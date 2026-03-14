from __future__ import annotations

from typing import Any

from backend.routines.adaptive_scheduler import AdaptiveContext
from backend.routines.time_mode_engine import (
    RoutinePlan,
    RoutinePreferences,
    generate_next_unknown_time_block,
    generate_timeboxed_routine,
    generate_unknown_time_seed,
)


def _block_item_to_dict(item: Any) -> dict[str, Any]:
    return {
        "exercise_id": item.exercise_id,
        "prescription": item.prescription,
        "coaching_hint": item.coaching_hint,
    }


def routine_plan_to_dict(plan: RoutinePlan) -> dict[str, Any]:
    return {
        "duration_minutes": plan.duration_minutes,
        "total_duration_sec": plan.total_duration_sec,
        "library_version": plan.library_version,
        "blocks": [
            {
                "name": b.name,
                "mode": b.mode,
                "duration_sec": b.duration_sec,
                "items": [_block_item_to_dict(i) for i in b.items],
                "voice_script": b.voice_script,
            }
            for b in plan.blocks
        ],
    }


def next_block_to_dict(block: Any) -> dict[str, Any]:
    return {
        "name": block.name,
        "mode": block.mode,
        "duration_sec": block.duration_sec,
        "items": [_block_item_to_dict(i) for i in block.items],
        "voice_script": block.voice_script,
    }


def generate_initial_plan(
    *,
    duration_minutes: int | None,
    equipment_available: list[str] | tuple[str, ...] = (),
    prefer_low_impact: bool = False,
    level: str | None = None,
) -> dict[str, Any]:
    prefs = RoutinePreferences(
        equipment_available=tuple(str(e) for e in equipment_available),
        prefer_low_impact=bool(prefer_low_impact),
        level=level,
    )

    if duration_minutes in (1, 5, 12, 15, 20, 30):
        try:
            plan = generate_timeboxed_routine(duration_minutes, prefs=prefs)
            out = routine_plan_to_dict(plan)
            out["mode"] = "timeboxed"
            return out
        except ValueError:
            # If timeboxed routine fails, fall back to unknown time mode
            pass

    plan = generate_unknown_time_seed(prefs=prefs)
    out = routine_plan_to_dict(plan)
    out["mode"] = "unknown_time"
    return out


def generate_adaptive_block(
    *,
    history: list[str],
    time_remaining_sec: int | None,
    recent_form_score: float | None,
    recent_fatigue: float | None,
    equipment_available: list[str] | tuple[str, ...] = (),
    prefer_low_impact: bool = False,
    level: str | None = None,
    block_duration_sec: int = 120,
) -> dict[str, Any]:
    ctx = AdaptiveContext(
        time_remaining_sec=time_remaining_sec,
        recent_form_score=recent_form_score,
        recent_fatigue=recent_fatigue,
        prefer_low_impact=bool(prefer_low_impact),
        equipment_available=tuple(str(e) for e in equipment_available),
        level=level,
    )

    block = generate_next_unknown_time_block(
        history=history,
        ctx=ctx,
        block_duration_sec=block_duration_sec,
    )
    out = next_block_to_dict(block)
    out["source"] = "deterministic"
    return out
