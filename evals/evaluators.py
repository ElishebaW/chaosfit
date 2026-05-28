"""Evaluators for Phase 1 evals — session summary, latency, rep count, correction quality."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

SETUP_LATENCY_THRESHOLD_MS = 500.0
REP_COUNT_TOLERANCE = 1

# Body-part keywords that make a correction specific rather than generic.
_BODY_PART_KEYWORDS = {
    "knee", "knees", "hip", "hips", "back", "spine", "shoulder", "shoulders",
    "elbow", "elbows", "wrist", "wrists", "chest", "core", "heel", "heels",
    "foot", "feet", "ankle", "ankles", "neck", "chin", "head", "glute", "glutes",
    "quad", "quads", "hamstring", "hamstrings", "torso", "arm", "arms", "leg", "legs",
}

_GENERIC_PHRASES = {
    "good job", "keep it up", "great job", "well done", "keep going",
    "nice work", "you're doing great", "great form", "looking good",
}


@dataclass
class EvalResult:
    case_id: str
    evaluator: str
    score: float  # 0.0 = fail, 1.0 = pass
    reason: str
    expected_pass: bool

    @property
    def passed(self) -> bool:
        return (self.score >= 0.5) == self.expected_pass


def eval_summary_completeness(case_id: str, output: dict[str, Any], expected_pass: bool) -> EvalResult:
    """Score whether session summary output has all required non-null, non-zero fields."""
    missing: list[str] = []
    if not output.get("exercise_type"):
        missing.append("exercise_type")
    rep_count = output.get("rep_count")
    if rep_count is None or rep_count <= 0:
        missing.append("rep_count>0")

    score = 0.0 if missing else 1.0
    reason = f"Missing or zero: {missing}" if missing else "All required fields present"
    return EvalResult(
        case_id=case_id,
        evaluator="summary_completeness",
        score=score,
        reason=reason,
        expected_pass=expected_pass,
    )


def eval_setup_latency(
    case_id: str,
    latency_ms: float,
    expected_pass: bool,
    threshold_ms: float = SETUP_LATENCY_THRESHOLD_MS,
) -> EvalResult:
    """Score whether session_setup latency is under the acceptable threshold."""
    score = 1.0 if latency_ms <= threshold_ms else 0.0
    op = "<=" if score == 1.0 else ">"
    reason = f"{latency_ms:.0f}ms {op} {threshold_ms:.0f}ms threshold"
    return EvalResult(
        case_id=case_id,
        evaluator="setup_latency",
        score=score,
        reason=reason,
        expected_pass=expected_pass,
    )


def eval_rep_count_accuracy(
    case_id: str,
    actual: int,
    expected: int,
    expected_pass: bool,
    tolerance: int = REP_COUNT_TOLERANCE,
) -> EvalResult:
    """Score whether the rep count is within ±tolerance of the expected count.

    When expected=0, tolerance is forced to 0 — any non-zero count is a false positive.
    """
    effective_tolerance = 0 if expected == 0 else tolerance
    delta = abs(actual - expected)
    score = 1.0 if delta <= effective_tolerance else 0.0
    reason = f"actual={actual}, expected={expected}, delta={delta} ({'within' if score == 1.0 else 'exceeds'} ±{effective_tolerance})"
    return EvalResult(
        case_id=case_id,
        evaluator="rep_count_accuracy",
        score=score,
        reason=reason,
        expected_pass=expected_pass,
    )


def eval_correction_specificity(
    case_id: str,
    corrections: list[str],
    expected_pass: bool,
) -> EvalResult:
    """
    Score whether corrections are specific (name a body part) and not generic encouragement.

    Passes when:
    - corrections list is empty (no corrections needed — valid for clean sessions), OR
    - every correction contains a body-part keyword AND none match a generic phrase
    """
    if not corrections:
        return EvalResult(
            case_id=case_id,
            evaluator="correction_specificity",
            score=1.0,
            reason="No corrections — valid for clean session",
            expected_pass=expected_pass,
        )

    generic_found: list[str] = []
    no_body_part: list[str] = []

    for correction in corrections:
        lower = correction.lower()
        if any(phrase in lower for phrase in _GENERIC_PHRASES):
            generic_found.append(correction)
        elif not any(kw in lower for kw in _BODY_PART_KEYWORDS):
            no_body_part.append(correction)

    counts = Counter(c.lower().strip() for c in corrections)
    repeated = [text for text, count in counts.items() if count >= 3]

    if generic_found:
        reason = f"Generic phrases found: {generic_found}"
        score = 0.0
    elif no_body_part:
        reason = f"No body-part keyword: {no_body_part}"
        score = 0.0
    elif repeated:
        reason = f"Correction repeated 3+ times without new error: {repeated[:2]}"
        score = 0.0
    else:
        reason = f"All {len(corrections)} correction(s) are specific and non-repetitive"
        score = 1.0

    return EvalResult(
        case_id=case_id,
        evaluator="correction_specificity",
        score=score,
        reason=reason,
        expected_pass=expected_pass,
    )


def eval_interruption_integrity(
    case_id: str,
    adk_interruption_count: int,
    interruption_count: int,
    expected_pass: bool,
) -> EvalResult:
    """
    Score whether interruption_count matches the number of ADK coach interruptions.

    interruption_count = ADK event.interrupted count (model speech cut off mid-turn).
    pause_count is a separate summary field for user-initiated pauses — not checked here.
    """
    score = 1.0 if interruption_count == adk_interruption_count else 0.0
    reason = (
        f"interruption_count={interruption_count} matches adk_interruption_count={adk_interruption_count}"
        if score == 1.0
        else f"interruption_count={interruption_count} != adk_interruption_count={adk_interruption_count} (inflated — F-1 pattern)"
    )
    return EvalResult(
        case_id=case_id,
        evaluator="interruption_integrity",
        score=score,
        reason=reason,
        expected_pass=expected_pass,
    )
