"""Evaluators for Phase 1 Group 4 — score trace outputs against ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SETUP_LATENCY_THRESHOLD_MS = 500.0


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
