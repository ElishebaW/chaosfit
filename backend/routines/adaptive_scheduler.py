from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal


LibraryLevel = Literal["beginner", "intermediate", "advanced"]
LibraryMovement = Literal["squat", "hinge", "lunge", "push", "pull", "carry", "core", "cardio", "mobility"]
LibraryModality = Literal["strength", "core", "cardio", "mobility"]


@dataclass(frozen=True)
class Exercise:
    id: str
    name: str
    modality: str
    movement: str
    level: str
    equipment: tuple[str, ...]
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...]
    default_set: dict[str, Any]
    coaching: dict[str, Any]
    common_mistakes: list[dict[str, Any]]
    safety_notes: tuple[str, ...]
    regressions: tuple[str, ...]
    progressions: tuple[str, ...]
    gemini: dict[str, Any]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Exercise":
        return Exercise(
            id=str(d["id"]),
            name=str(d["name"]),
            modality=str(d["modality"]),
            movement=str(d["movement"]),
            level=str(d.get("level", "beginner")),
            equipment=tuple(d.get("equipment", []) or []),
            primary_muscles=tuple(d.get("primary_muscles", []) or []),
            secondary_muscles=tuple(d.get("secondary_muscles", []) or []),
            default_set=dict(d.get("default_set", {}) or {}),
            coaching=dict(d.get("coaching", {}) or {}),
            common_mistakes=list(d.get("common_mistakes", []) or []),
            safety_notes=tuple(d.get("safety_notes", []) or []),
            regressions=tuple(d.get("regressions", []) or []),
            progressions=tuple(d.get("progressions", []) or []),
            gemini=dict(d.get("gemini", {}) or {}),
        )


class ExerciseLibrary:
    def __init__(self, exercises: Iterable[Exercise], *, version: str = "unknown") -> None:
        self.version = version
        by_id: dict[str, Exercise] = {}
        for ex in exercises:
            if ex.id in by_id:
                raise ValueError(f"duplicate exercise id: {ex.id}")
            by_id[ex.id] = ex
        self._by_id = by_id

    def get(self, exercise_id: str) -> Exercise:
        try:
            return self._by_id[exercise_id]
        except KeyError as e:
            raise KeyError(f"unknown exercise_id: {exercise_id}") from e

    def ids(self) -> list[str]:
        return sorted(self._by_id.keys())

    def filter(
        self,
        *,
        modality: str | None = None,
        movement: str | None = None,
        level: str | None = None,
        equipment_available: set[str] | None = None,
    ) -> list[Exercise]:
        out: list[Exercise] = []
        for ex in self._by_id.values():
            if modality is not None and ex.modality != modality:
                continue
            if movement is not None and ex.movement != movement:
                continue
            if level is not None and ex.level != level:
                continue
            if equipment_available is not None:
                required = set(ex.equipment)
                if not required.issubset(equipment_available):
                    continue
            out.append(ex)
        return sorted(out, key=lambda e: e.id)


def _default_library_path() -> Path:
    return Path(__file__).resolve().parent / "exercise_library.json"


def validate_exercise_library_data(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("library JSON must be an object")
    if "exercises" not in data or not isinstance(data["exercises"], list):
        raise ValueError("library JSON must contain an 'exercises' array")
    for i, ex in enumerate(data["exercises"]):
        if not isinstance(ex, dict):
            raise ValueError(f"exercise at index {i} must be an object")
        for key in ("id", "name", "modality", "movement"):
            if key not in ex or not ex[key]:
                raise ValueError(f"exercise at index {i} missing required field '{key}'")


def load_exercise_library(library_path: str | Path | None = None) -> ExerciseLibrary:
    path = Path(library_path) if library_path is not None else _default_library_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    validate_exercise_library_data(raw)
    exercises = [Exercise.from_dict(d) for d in raw["exercises"]]
    return ExerciseLibrary(exercises, version=str(raw.get("version", "unknown")))


@dataclass(frozen=True)
class AdaptiveContext:
    """
    Signals coming from the live session layer.
    Keep this intentionally simple so Person 1 / Person 3 can populate it easily.
    """

    time_remaining_sec: int | None = None
    recent_form_score: float | None = None  # expected 0..1 (1 = great form)
    recent_fatigue: float | None = None  # expected 0..1 (1 = very fatigued)
    prefer_low_impact: bool = False
    equipment_available: tuple[str, ...] = ()
    level: str | None = None


@dataclass(frozen=True)
class BlockItem:
    exercise_id: str
    prescription: dict[str, Any]  # {"type":"reps",...} or {"type":"time",...}
    coaching_hint: str | None = None


@dataclass(frozen=True)
class NextBlock:
    name: str
    mode: Literal["warmup", "main", "finisher", "cooldown"]
    duration_sec: int
    items: tuple[BlockItem, ...]
    voice_script: str


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _pick_candidate_ids(
    library: ExerciseLibrary,
    *,
    allow_modality: set[str] | None = None,
    allow_movement: set[str] | None = None,
    equipment_available: set[str],
) -> list[str]:
    ids: list[str] = []
    for ex_id in library.ids():
        ex = library.get(ex_id)
        if allow_modality is not None and ex.modality not in allow_modality:
            continue
        if allow_movement is not None and ex.movement not in allow_movement:
            continue
        if set(ex.equipment).issubset(equipment_available):
            ids.append(ex_id)
    return ids


def choose_next_exercise_id(
    library: ExerciseLibrary,
    *,
    history: list[str] | None = None,
    ctx: AdaptiveContext | None = None,
    allow_modality: set[str] | None = None,
    allow_movement: set[str] | None = None,
) -> str:
    history = history or []
    ctx = ctx or AdaptiveContext()

    equipment = set(ctx.equipment_available)
    candidates = _pick_candidate_ids(
        library,
        allow_modality=allow_modality,
        allow_movement=allow_movement,
        equipment_available=equipment,
    )
    if not candidates:
        # fall back to anything that matches equipment
        candidates = _pick_candidate_ids(library, equipment_available=equipment)
    if not candidates:
        raise ValueError("no exercises available for the given equipment constraints")

    last_id = history[-1] if history else None
    last_movement = library.get(last_id).movement if last_id else None

    fatigue = _clamp01(ctx.recent_fatigue) if ctx.recent_fatigue is not None else 0.4
    form = _clamp01(ctx.recent_form_score) if ctx.recent_form_score is not None else 0.7

    # Heuristic: if fatigue high or form low, bias toward lower-impact/core control.
    if fatigue >= 0.75 or form <= 0.45:
        preferred = ["dead_bug", "bird_dog", "plank", "side_plank", "glute_bridge", "step_jack"]
        for ex_id in preferred:
            if ex_id in candidates and ex_id != last_id:
                return ex_id

    # Heuristic: avoid repeating the same movement pattern back-to-back.
    if last_movement is not None:
        non_repeating = [c for c in candidates if library.get(c).movement != last_movement]
        if non_repeating:
            candidates = non_repeating

    # Low-impact preference: steer away from high-bounce cardio.
    if ctx.prefer_low_impact:
        avoid = {"jumping_jack"}
        filtered = [c for c in candidates if c not in avoid]
        if filtered:
            candidates = filtered

    # Time-aware finisher: if very short time remaining, pick something "closeable".
    if ctx.time_remaining_sec is not None and ctx.time_remaining_sec <= 75:
        for ex_id in ("wall_sit", "plank", "mountain_climber", "step_jack"):
            if ex_id in candidates:
                return ex_id

    # Deterministic pick: rotate through candidates based on history length.
    idx = len(history) % len(candidates)
    return candidates[idx]


def _voice_for_block(library: ExerciseLibrary, items: list[BlockItem], *, block_name: str) -> str:
    lines: list[str] = [block_name]
    for it in items:
        ex = library.get(it.exercise_id)
        start_prompt = ex.gemini.get("start_prompt") or ex.gemini.get("one_sentence") or ex.name
        lines.append(f"- {ex.name}: {start_prompt}")
    return "\n".join(lines)


def recommend_next_block(
    library: ExerciseLibrary,
    *,
    history: list[str] | None = None,
    ctx: AdaptiveContext | None = None,
    block_duration_sec: int = 120,
) -> NextBlock:
    """
    Unknown-time mode: returns a short block (~2 minutes) that can be repeated until the session ends.
    """
    history = history or []
    ctx = ctx or AdaptiveContext()

    # Simple 2-item alternating block: one strength/control + one cardio/core.
    ex1 = choose_next_exercise_id(
        library,
        history=history,
        ctx=ctx,
        allow_modality={"strength", "core"},
    )
    history2 = history + [ex1]
    ex2 = choose_next_exercise_id(
        library,
        history=history2,
        ctx=ctx,
        allow_modality={"cardio", "core"},
    )

    items = [
        BlockItem(exercise_id=ex1, prescription=library.get(ex1).default_set),
        BlockItem(exercise_id=ex2, prescription=library.get(ex2).default_set),
    ]
    voice = _voice_for_block(library, items, block_name="Next block")
    return NextBlock(
        name="Adaptive Block",
        mode="main",
        duration_sec=int(block_duration_sec),
        items=tuple(items),
        voice_script=voice,
    )


def dump_library_summary(library: ExerciseLibrary) -> dict[str, Any]:
    return {
        "version": library.version,
        "count": len(library.ids()),
        "by_modality": {
            m: len(library.filter(modality=m))
            for m in sorted({library.get(i).modality for i in library.ids()})
        },
        "by_movement": {
            m: len(library.filter(movement=m))
            for m in sorted({library.get(i).movement for i in library.ids()})
        },
    }


if __name__ == "__main__":
    lib = load_exercise_library()
    print(json.dumps(dump_library_summary(lib), indent=2))
    block = recommend_next_block(lib, history=["air_squat", "push_up"], ctx=AdaptiveContext(time_remaining_sec=None))
    print()
    print(block.voice_script)
