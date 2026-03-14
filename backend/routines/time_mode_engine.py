from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .adaptive_scheduler import (
    AdaptiveContext,
    BlockItem,
    ExerciseLibrary,
    NextBlock,
    load_exercise_library,
    recommend_next_block,
)


@dataclass(frozen=True)
class RoutineBlock:
    name: str
    mode: Literal["warmup", "main", "finisher", "cooldown"]
    duration_sec: int
    items: tuple[BlockItem, ...]
    voice_script: str


@dataclass(frozen=True)
class RoutinePlan:
    duration_minutes: int | None  # None for unknown time mode
    total_duration_sec: int | None
    blocks: tuple[RoutineBlock, ...]
    library_version: str


@dataclass(frozen=True)
class RoutinePreferences:
    equipment_available: tuple[str, ...] = ()
    prefer_low_impact: bool = False
    level: str | None = None


def _block_voice(library: ExerciseLibrary, title: str, items: list[BlockItem]) -> str:
    lines = [title]
    for it in items:
        ex = library.get(it.exercise_id)
        prompt = ex.gemini.get("start_prompt") or ex.gemini.get("one_sentence") or ex.name
        lines.append(f"- {ex.name}: {prompt}")
    return "\n".join(lines)


def _choose_if_available(library: ExerciseLibrary, ex_id: str, *, equipment_available: set[str]) -> str | None:
    ex = library.get(ex_id)
    if set(ex.equipment).issubset(equipment_available):
        return ex_id
    return None


def generate_timeboxed_routine(
    duration_minutes: int,
    *,
    prefs: RoutinePreferences | None = None,
    library: ExerciseLibrary | None = None,
) -> RoutinePlan:
    """
    Generates a simple, deterministic plan for demos:
    - 1 minute: 0.25m warmup, 0.5m main, 0.25m cooldown
    - 5 minutes: 1m warmup, 3m main, 1m cooldown
    - 12 minutes: 2m warmup, 8m main, 2m cooldown
    - 15 minutes: 2.5m warmup, 10m main, 2.5m cooldown
    - 20 minutes: 3m warmup, 14m main, 3m cooldown
    - 30 minutes: 5m warmup, 20m main, 5m cooldown
    """
    prefs = prefs or RoutinePreferences()
    library = library or load_exercise_library()

    if duration_minutes not in (1, 5, 12, 15, 20, 30):
        raise ValueError("duration_minutes must be one of: 1, 5, 12, 15, 20, 30")

    equipment = set(prefs.equipment_available)
    ctx = AdaptiveContext(
        time_remaining_sec=duration_minutes * 60,
        prefer_low_impact=prefs.prefer_low_impact,
        equipment_available=prefs.equipment_available,
        level=prefs.level,
    )

    if duration_minutes == 1:
        warmup_sec, main_sec, cooldown_sec = 15, 30, 15
    elif duration_minutes == 5:
        warmup_sec, main_sec, cooldown_sec = 60, 180, 60
    elif duration_minutes == 12:
        warmup_sec, main_sec, cooldown_sec = 120, 480, 120
    elif duration_minutes == 15:
        warmup_sec, main_sec, cooldown_sec = 150, 600, 150
    elif duration_minutes == 20:
        warmup_sec, main_sec, cooldown_sec = 180, 840, 180
    else:  # 30 minutes
        warmup_sec, main_sec, cooldown_sec = 300, 1200, 300

    # Warmup: low-impact cardio + hinge + squat pattern
    cardio = "step_jack" if prefs.prefer_low_impact else "jumping_jack"
    warmup_ids = [
        _choose_if_available(library, cardio, equipment_available=equipment),
        _choose_if_available(library, "good_morning", equipment_available=equipment),
        _choose_if_available(library, "air_squat", equipment_available=equipment),
    ]
    warmup_items = [BlockItem(exercise_id=eid, prescription=library.get(eid).default_set) for eid in warmup_ids if eid]
    warmup_voice = _block_voice(library, "Warmup", warmup_items)

    # Main: simple circuit with variety
    main_candidates = [
        "push_up",
        "reverse_lunge",
        "glute_bridge",
        "mountain_climber",
        "dead_bug",
    ]
    main_items: list[BlockItem] = []
    for eid in main_candidates:
        picked = _choose_if_available(library, eid, equipment_available=equipment)
        if picked:
            main_items.append(BlockItem(exercise_id=picked, prescription=library.get(picked).default_set))
    if not main_items:
        # absolute fallback: ask adaptive scheduler for a block
        adaptive = recommend_next_block(library, history=[], ctx=ctx, block_duration_sec=min(120, main_sec))
        main_items = list(adaptive.items)
    main_voice = _block_voice(library, "Main circuit", main_items)

    # Cooldown: breathing + low intensity core/legs (demo-friendly)
    cooldown_candidates = ["plank", "glute_bridge", "chair_squat"]
    cooldown_items: list[BlockItem] = []
    for eid in cooldown_candidates:
        picked = _choose_if_available(library, eid, equipment_available=equipment)
        if picked:
            # make cooldown gentler by shortening time-based holds slightly
            presc: dict[str, Any] = dict(library.get(picked).default_set)
            if presc.get("type") == "time":
                presc["seconds"] = int(min(presc.get("seconds", 20), 20))
            cooldown_items.append(BlockItem(exercise_id=picked, prescription=presc))
    cooldown_voice = _block_voice(library, "Cooldown (easy pace)", cooldown_items)

    blocks = (
        RoutineBlock("Warmup", "warmup", warmup_sec, tuple(warmup_items), warmup_voice),
        RoutineBlock("Main", "main", main_sec, tuple(main_items), main_voice),
        RoutineBlock("Cooldown", "cooldown", cooldown_sec, tuple(cooldown_items), cooldown_voice),
    )
    return RoutinePlan(
        duration_minutes=duration_minutes,
        total_duration_sec=duration_minutes * 60,
        blocks=blocks,
        library_version=library.version,
    )


def generate_unknown_time_seed(
    *,
    prefs: RoutinePreferences | None = None,
    library: ExerciseLibrary | None = None,
) -> RoutinePlan:
    """
    Unknown time mode: return an initial warmup block and instructions to keep requesting
    `recommend_next_block(...)` until the session ends.
    """
    prefs = prefs or RoutinePreferences()
    library = library or load_exercise_library()
    equipment = set(prefs.equipment_available)

    cardio = "step_jack" if prefs.prefer_low_impact else "jumping_jack"
    warmup_ids = [
        _choose_if_available(library, cardio, equipment_available=equipment),
        _choose_if_available(library, "good_morning", equipment_available=equipment),
        _choose_if_available(library, "air_squat", equipment_available=equipment),
    ]
    warmup_items = [BlockItem(exercise_id=eid, prescription=library.get(eid).default_set) for eid in warmup_ids if eid]
    warmup_voice = _block_voice(
        library,
        "Unknown-time warmup (then we’ll adapt block-by-block)",
        warmup_items,
    )
    blocks = (RoutineBlock("Warmup", "warmup", 90, tuple(warmup_items), warmup_voice),)
    return RoutinePlan(duration_minutes=None, total_duration_sec=None, blocks=blocks, library_version=library.version)


def generate_next_unknown_time_block(
    *,
    history: list[str],
    ctx: AdaptiveContext,
    block_duration_sec: int = 120,
    library: ExerciseLibrary | None = None,
) -> NextBlock:
    library = library or load_exercise_library()
    return recommend_next_block(library, history=history, ctx=ctx, block_duration_sec=block_duration_sec)


if __name__ == "__main__":
    lib = load_exercise_library()
    plan = generate_timeboxed_routine(12, prefs=RoutinePreferences(prefer_low_impact=True), library=lib)
    for b in plan.blocks:
        print()
        print(f"[{b.mode.upper()}] {b.name} ({b.duration_sec}s)")
        print(b.voice_script)

    seed = generate_unknown_time_seed(prefs=RoutinePreferences(prefer_low_impact=True), library=lib)
    print()
    print("Unknown-time seed:")
    print(seed.blocks[0].voice_script)
