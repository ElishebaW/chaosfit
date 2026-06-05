#!/usr/bin/env python3
"""
Trace harness.

Drives WebSocket sessions against the running server to generate Langfuse trace data
and assert correctness of key behaviors:
  1. Session summary is present and complete (exercise_type, rep_count non-null).
  2. Coach is ready (session_state:active) before sending any model content.
  3. Passive difficulty adjustment fires and produces an adjust_difficulty span.

This is NOT a CI test. Run it manually against a running server.

Usage:
    # Against local server (start with: uv run uvicorn backend.main:app --port 8080)
    python test/trace_harness.py

    # Against the deployed Cloud Run URL
    CHAOSFIT_WS_URL=wss://your-cloud-run-url python test/trace_harness.py

    # Single scenario, 3 runs
    python test/trace_harness.py --scenario session_with_interruption --runs 3

Scenarios:
    clean_session             — normal session, 5 frames, one exercise, clean end
    session_with_interruption — pause mid-session, resume, then end
    misidentified_exercise    — exercise_update claims a different exercise than context implies
    difficulty_adjustment     — sends high-fatigue signal to trigger passive difficulty adjustment
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from typing import Any

import websockets
from dotenv import load_dotenv
from langfuse import Langfuse, observe
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_langfuse = Langfuse()

# Minimal valid 1×1 JPEG — satisfies base64 decode without sending real video data
_FRAME_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDB"
    "kSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAAR"
    "CAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAA"
    "AAAAAAAAAAAAAP/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAA"
    "AAAAAAAP/aAAwDAQACEQMRAD8AJQAB/9k="
)

# ---------------------------------------------------------------------------
# Scenario drivers — each sends a distinct sequence of WebSocket messages
# ---------------------------------------------------------------------------

async def _scenario_clean_session(ws: Any, _session_id: str) -> None:
    """Normal session: 5 video frames → exercise update → end."""
    for _ in range(5):
        await ws.send(json.dumps({
            "type": "video",
            "capturedAt": time.time() * 1000,
            "data": _FRAME_B64,
            "mimeType": "image/jpeg",
        }))
        await asyncio.sleep(0.2)

    await ws.send(json.dumps({
        "type": "exercise_update",
        "exercise_id": "push_up",
        "exercise_type": "push_up",
        "rep_count": 10,
        "form_corrections": ["keep back straight"],
    }))

    await ws.send(json.dumps({
        "type": "end",
        "exercise_type": "push_up",
        "rep_count": 10,
        "session_goal": "trace-harness: clean_session",
    }))


async def _scenario_session_with_interruption(ws: Any, _session_id: str) -> None:
    """One pause/resume mid-session then end."""
    for _ in range(3):
        await ws.send(json.dumps({
            "type": "video",
            "capturedAt": time.time() * 1000,
            "data": _FRAME_B64,
            "mimeType": "image/jpeg",
        }))
        await asyncio.sleep(0.2)

    await ws.send(json.dumps({"type": "pause", "reason": "baby_crying"}))
    await asyncio.sleep(0.5)
    await ws.send(json.dumps({"type": "resume"}))

    for _ in range(3):
        await ws.send(json.dumps({
            "type": "video",
            "capturedAt": time.time() * 1000,
            "data": _FRAME_B64,
            "mimeType": "image/jpeg",
        }))
        await asyncio.sleep(0.2)

    await ws.send(json.dumps({
        "type": "exercise_update",
        "exercise_id": "air_squat",
        "exercise_type": "air_squat",
        "rep_count": 8,
        "form_corrections": [],
    }))

    await ws.send(json.dumps({
        "type": "end",
        "exercise_type": "air_squat",
        "rep_count": 8,
        "session_goal": "trace-harness: session_with_interruption",
    }))


async def _scenario_misidentified_exercise(ws: Any, _session_id: str) -> None:
    """
    Exercise mismatch: frames are sent but exercise_update reports 'lunge'
    while context implied 'squat'. Surfaces detection inconsistency in traces.
    """
    for _ in range(5):
        await ws.send(json.dumps({
            "type": "video",
            "capturedAt": time.time() * 1000,
            "data": _FRAME_B64,
            "mimeType": "image/jpeg",
        }))
        await asyncio.sleep(0.2)

    await ws.send(json.dumps({
        "type": "exercise_update",
        "exercise_id": "lunge",
        "exercise_type": "lunge",
        "rep_count": 5,
        "form_corrections": ["keep front knee over ankle", "upright torso"],
    }))

    await ws.send(json.dumps({
        "type": "end",
        "exercise_type": "lunge",
        "rep_count": 5,
        "session_goal": "trace-harness: misidentified_exercise",
    }))


_DIFFICULTY_ROUTINE_PLAN: dict[str, Any] = {
    "blocks": [
        {
            "name": "Main",
            "mode": "main",
            "duration_sec": 120,
            "items": [
                {
                    "exercise_id": "push_up",
                    "prescription": {"type": "reps", "reps_min": 8, "reps_max": 12, "rest_seconds": 30},
                    "coaching_hint": "keep core tight",
                },
            ],
        },
        {
            "name": "Cooldown",
            "mode": "cooldown",
            "duration_sec": 60,
            "items": [
                {
                    "exercise_id": "plank",
                    "prescription": {"type": "time", "seconds": 30, "rest_seconds": 15},
                    "coaching_hint": "breathe steadily",
                },
            ],
        },
    ]
}


async def _scenario_difficulty_adjustment(ws: Any, _session_id: str) -> None:
    """Trigger passive difficulty adjustment via high-fatigue signal.

    Step 1: sends a routine plan so there are pending blocks to mutate.
    Step 2: sends fatigue=0.85 — the server's passive signal check fires "easier"
            *after* fatigue is written to state, producing an adjust_difficulty Langfuse span.
    """
    # Step 1: load routine plan (current_block_index=0, so block 1 is pending)
    await ws.send(json.dumps({
        "type": "exercise_update",
        "routine_plan": _DIFFICULTY_ROUTINE_PLAN,
        "exercise_id": "push_up",
        "rep_count": 3,
    }))
    await asyncio.sleep(0.3)

    # Step 2: high fatigue — triggers "easier" passive signal
    await ws.send(json.dumps({
        "type": "exercise_update",
        "fatigue": 0.85,
        "rep_count": 2,
        "exercise_id": "push_up",
    }))
    await asyncio.sleep(0.5)

    await ws.send(json.dumps({
        "type": "end",
        "exercise_type": "push_up",
        "rep_count": 5,
        "session_goal": "trace-harness: difficulty_adjustment",
    }))


_SCENARIOS: dict[str, Any] = {
    "clean_session": _scenario_clean_session,
    "session_with_interruption": _scenario_session_with_interruption,
    "misidentified_exercise": _scenario_misidentified_exercise,
    "difficulty_adjustment": _scenario_difficulty_adjustment,
}


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

_READY_KEYWORDS = {"ready", "begin", "start", "let's", "go ahead", "whenever you're"}
_CORRECTION_KEYWORDS = {"keep", "lower", "straighten", "tuck", "chest up", "hips back", "knees", "back straight"}


def _extract_adk_text_parts(msg: dict) -> list[str]:
    """Extract text strings from an ADK LiveServerMessage dict."""
    server_content = msg.get("serverContent") or msg.get("server_content")
    if not isinstance(server_content, dict):
        return []
    model_turn = server_content.get("modelTurn") or server_content.get("model_turn")
    if not isinstance(model_turn, dict):
        return []
    return [
        p["text"]
        for p in model_turn.get("parts", [])
        if isinstance(p, dict) and p.get("text")
    ]


def _has_model_content(msg: dict) -> bool:
    server_content = msg.get("serverContent") or msg.get("server_content")
    if not isinstance(server_content, dict):
        return False
    return bool(server_content.get("modelTurn") or server_content.get("model_turn"))


def _assert_websocket_events(session_id: str, received: list[dict]) -> list[str]:
    """
    Run assertions on received WebSocket events.
    Returns a list of failure strings (empty = all pass).
    """
    failures: list[str] = []

    # --- Assertion 1: session must end cleanly ----------------------------------
    ended = any(
        m.get("type") == "session_state" and m.get("status") == "ended"
        for m in received
    )
    if not ended:
        failures.append(
            "summary: session_state:ended not received — session timed out or crashed "
            "before summary was written"
        )

    # --- Assertion 2: session_state:active before any model content -------------
    # session_state:active signals the coach is connected and ready.
    # Model content arriving before this means corrections could fire prematurely.
    active_index: int | None = None
    first_content_index: int | None = None
    for i, msg in enumerate(received):
        if msg.get("type") == "session_state" and msg.get("status") == "active":
            if active_index is None:
                active_index = i
        if first_content_index is None and _has_model_content(msg):
            first_content_index = i

    if first_content_index is not None and active_index is None:
        failures.append(
            "ready: coach sent model content but session_state:active was never received — "
            "session setup may have been skipped"
        )
    elif (
        first_content_index is not None
        and active_index is not None
        and first_content_index < active_index
    ):
        failures.append(
            f"ready: coach sent model content at event #{first_content_index} before "
            f"session_state:active at event #{active_index} — premature corrections"
        )

    # --- Assertion 3: if the model returned text, corrections come after ready --
    # Native-audio responses carry no text parts, so this check is skipped silently
    # when the model returns audio only.
    seen_ready = False
    for msg in received:
        for text in _extract_adk_text_parts(msg):
            text_lower = text.lower()
            if any(kw in text_lower for kw in _READY_KEYWORDS):
                seen_ready = True
            hit = next((kw for kw in _CORRECTION_KEYWORDS if kw in text_lower), None)
            if hit and not seen_ready:
                failures.append(
                    f"ready: coach gave correction '{hit}' in text before a ready/begin "
                    f"signal: '{text[:80]}'"
                )
                break

    return failures


def _langfuse_rest(path: str, params: dict | None = None) -> dict:
    """Call the Langfuse REST API. Langfuse v4 SDK has no query methods — REST is the right path."""
    import httpx
    base = os.getenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com").rstrip("/")
    auth = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
    r = httpx.get(f"{base}{path}", params=params or {}, auth=auth, timeout=15)
    r.raise_for_status()
    return r.json()


async def _check_langfuse_difficulty_adjustments(successful: list[tuple[str, str]]) -> list[str]:
    """Assert that adjust_difficulty observations exist for difficulty_adjustment scenarios."""
    failures: list[str] = []
    relevant = [(sc, sid) for sc, sid in successful if sc == "difficulty_adjustment"]
    if not relevant:
        return failures
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        failures.append("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set — skipping difficulty check")
        return failures
    for scenario, session_id in relevant:
        label = f"[{scenario}/{session_id[:16]}]"
        try:
            obs = _langfuse_rest(
                "/api/public/observations",
                {"sessionId": session_id, "name": "adjust_difficulty", "limit": 1},
            )
            if not obs.get("data"):
                failures.append(
                    f"{label} adjust_difficulty: no adjust_difficulty observation in Langfuse "
                    "(passive signal may not have fired — check server logs)"
                )
                continue
            output = obs["data"][0].get("output") or {}
            if not output.get("direction"):
                failures.append(f"{label} adjust_difficulty: direction missing from span output")
            if not output.get("trigger"):
                failures.append(f"{label} adjust_difficulty: trigger missing from span output")
        except Exception as exc:
            failures.append(f"{label} Langfuse REST query failed: {exc}")
    return failures


async def _check_langfuse_summaries(successful: list[tuple[str, str]]) -> list[str]:
    """
    Query Langfuse REST API for session_summary_generation observations and assert completeness.

    successful: list of (scenario, session_id) for runs that completed without WS error.
    Call after _langfuse.flush() so server traces have time to land.
    """
    failures: list[str] = []
    if not successful:
        return failures

    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        failures.append("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set — skipping summary check")
        return failures

    for scenario, session_id in successful:
        label = f"[{scenario}/{session_id[:16]}]"
        try:
            # Query observations directly by session_id — the @observe spans create
            # their own top-level traces (separate from ADK OTel traces), so we can't
            # find them by walking the ADK trace tree.
            obs = _langfuse_rest(
                "/api/public/observations",
                {"sessionId": session_id, "name": "session_summary_generation", "limit": 1},
            )
            summary_output: dict | None = None
            if obs.get("data"):
                summary_output = obs["data"][0].get("output") or {}

            if summary_output is None:
                failures.append(
                    f"{label} summary: no session_summary_generation observation in Langfuse "
                    "(server may not be flushing — verify LANGFUSE_* env vars on the server process)"
                )
                continue

            if not summary_output.get("exercise_type"):
                failures.append(f"{label} summary: exercise_type is null")
            rep_count = summary_output.get("rep_count")
            if rep_count is None or rep_count <= 0:
                failures.append(f"{label} summary: rep_count is 0 or null")
        except Exception as exc:
            failures.append(f"{label} Langfuse REST query failed: {exc}")

    return failures


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def _drain(ws: Any, received: list[dict]) -> None:
    try:
        async for raw in ws:
            try:
                received.append(json.loads(raw))
            except Exception:
                pass
    except Exception:
        pass


async def _run_scenario(base_url: str, scenario: str, run_index: int) -> dict[str, Any]:
    session_id = f"trace-{scenario[:8]}-{run_index}-{uuid.uuid4().hex[:6]}"
    ws_url = f"{base_url}/ws/trace-harness/{session_id}"
    received: list[dict] = []
    error: str | None = None

    try:
        async with websockets.connect(ws_url) as ws:
            drain = asyncio.create_task(_drain(ws, received))
            await _SCENARIOS[scenario](ws, session_id)
            await asyncio.sleep(1.5)
            drain.cancel()
    except Exception as exc:
        error = str(exc)

    assertion_failures = _assert_websocket_events(session_id, received) if not error else []

    return {
        "scenario": scenario,
        "run_index": run_index,
        "session_id": session_id,
        "events_received": len(received),
        "event_types": [m.get("type") for m in received],
        "received": received,
        "error": error,
        "assertion_failures": assertion_failures,
    }


@observe(name="trace_harness_scenario")
async def _traced_scenario(base_url: str, scenario: str, run_index: int) -> dict[str, Any]:
    result = await _run_scenario(base_url, scenario, run_index)
    # Strip received from the observed output to keep traces lean
    return {k: v for k, v in result.items() if k != "received"}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--url",
        default=os.getenv("CHAOSFIT_WS_URL", "ws://localhost:8080"),
        help="WebSocket base URL (default: ws://localhost:8080 or $CHAOSFIT_WS_URL)",
    )
    parser.add_argument(
        "--runs", type=int, default=10,
        help="Total number of runs distributed across scenarios (default: 10)",
    )
    parser.add_argument(
        "--scenario", choices=[*_SCENARIOS, "all"], default="all",
        help="Run one scenario or all (default: all)",
    )
    args = parser.parse_args()

    active = list(_SCENARIOS) if args.scenario == "all" else [args.scenario]

    print(f"Server    : {args.url}")
    print(f"Scenarios : {active}")
    print(f"Total runs: {args.runs}\n")

    results: list[dict] = []
    for i in range(args.runs):
        scenario = active[i % len(active)]
        print(f"[{i + 1:02d}/{args.runs}] {scenario} ...", end="  ", flush=True)
        result = await _traced_scenario(args.url, scenario, i)
        results.append(result)
        if result["error"]:
            print(f"FAIL — {result['error'][:80]}")
        elif result["assertion_failures"]:
            print(f"ASSERT FAIL — {result['events_received']} events, session={result['session_id']}")
            for f in result["assertion_failures"]:
                print(f"    ! {f}")
        else:
            print(f"OK — {result['events_received']} events, session={result['session_id']}")

    ws_passed = sum(1 for r in results if not r["error"] and not r["assertion_failures"])
    ws_assert_failed = sum(1 for r in results if not r["error"] and r["assertion_failures"])
    ws_errored = sum(1 for r in results if r["error"])
    print(f"\nWebSocket results: {ws_passed} passed  |  {ws_assert_failed} assertion failures  |  {ws_errored} errors")

    # Flush harness traces, then wait for server's BatchSpanProcessor to export.
    print("\nFlushing Langfuse traces ...", end="  ", flush=True)
    _langfuse.flush()
    await asyncio.sleep(5)
    print("done")

    successful = [
        (r["scenario"], r["session_id"])
        for r in results
        if not r["error"]
    ]
    print(f"Checking Langfuse summaries for {len(successful)} sessions ...")
    lf_failures = await _check_langfuse_summaries(successful)
    if lf_failures:
        print(f"  {len(lf_failures)} Langfuse assertion(s) failed:")
        for f in lf_failures:
            print(f"    ! {f}")
    else:
        print(f"  All {len(successful)} session summaries look complete in Langfuse.")

    print("Checking Langfuse difficulty-adjustment spans ...")
    diff_failures = await _check_langfuse_difficulty_adjustments(successful)
    if diff_failures:
        print(f"  {len(diff_failures)} difficulty-adjustment assertion(s) failed:")
        for f in diff_failures:
            print(f"    ! {f}")
    elif any(sc == "difficulty_adjustment" for sc, _ in successful):
        print(f"  adjust_difficulty spans confirmed in Langfuse.")

    total_failures = ws_assert_failed + ws_errored + len(lf_failures) + len(diff_failures)
    print(f"\n{'ALL CHECKS PASSED' if total_failures == 0 else f'{total_failures} check(s) failed — see above'}")
    print("Check https://us.cloud.langfuse.com for full traces.")


if __name__ == "__main__":
    asyncio.run(main())
