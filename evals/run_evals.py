#!/usr/bin/env python3
"""
Eval runner — Phase 1 Group 4.

Runs evaluators against dataset.json ground-truth cases. When Langfuse credentials
are present, posts scores back to the Langfuse dashboard for human review.

Usage:
    python -m evals.run_evals          # print results, exit 0
    python -m evals.run_evals --ci     # exit 1 if any case does not match expected outcome
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.session_utils import extract_end_summary
from evals.evaluators import EvalResult, eval_setup_latency, eval_summary_completeness


def _load_dataset() -> dict:
    return json.loads((Path(__file__).parent / "dataset.json").read_text())


def _post_scores_to_langfuse(results: list[EvalResult]) -> None:
    try:
        from langfuse import Langfuse

        lf = Langfuse()
        for r in results:
            lf.score(
                name=r.evaluator,
                value=r.score,
                comment=r.reason,
                data_type="NUMERIC",
                trace_id=f"eval-dataset-{r.case_id}",
            )
        lf.flush()
        print("  Scores posted to Langfuse.")
    except Exception as exc:
        print(f"  Langfuse score post skipped: {exc}")


def main(ci_mode: bool) -> int:
    dataset = _load_dataset()
    results: list[EvalResult] = []

    print("=== Session Summary Evals ===")
    for case in dataset["session_summary_cases"]:
        output = extract_end_summary(case["input"])
        result = eval_summary_completeness(case["id"], output, case["expected_pass"])
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.case_id}: {result.reason}")

    print("\n=== Setup Latency Evals ===")
    for case in dataset["setup_latency_cases"]:
        result = eval_setup_latency(case["id"], case["latency_ms"], case["expected_pass"])
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.case_id}: {result.reason}")

    failures = [r for r in results if not r.passed]
    print(f"\n{len(results) - len(failures)}/{len(results)} eval cases passed.")

    print("\n=== Langfuse Scoring ===")
    _post_scores_to_langfuse(results)

    if ci_mode and failures:
        print(f"\nCI: {len(failures)} eval(s) did not match expected outcome — failing build.")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ci", action="store_true", help="Exit 1 on unexpected eval outcome")
    args = parser.parse_args()
    sys.exit(main(ci_mode=args.ci))
