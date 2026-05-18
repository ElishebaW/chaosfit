#!/usr/bin/env python3
"""
Trace harness — Phase 1 Group 3/4.

Drives WebSocket sessions against the running server to generate Langfuse trace data
and assert correctness of two key behaviors:
  1. Session summary is present and complete (exercise_type, rep_count non-null).
  2. Coach is ready (session_state:active) before sending any model content.

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
from langfuse import Langfuse, get_client, observe
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


_SCENARIOS: dict[str, Any] = {
    "clean_session": _scenario_clean_session,
    "session_with_interruption": _scenario_session_with_interruption,
    "misidentified_exercise": _scenario_misidentified_exercise,
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


async def _check_langfuse_summaries(successful: list[tuple[str, str]]) -> list[str]:
    """
    Query Langfuse for session_summary_generation observations and assert completeness.

    successful: list of (scenario, session_id) for runs that completed without WS error.
    Traces take a moment to flush; call after _langfuse.flush().
    """
    failures: list[str] = []
    if not successful:
        return failures
    try:
        lf = get_client()
        for scenario, session_id in successful:
            label = f"[{scenario}/{session_id[:16]}]"
            try:
                # List traces for this session, then find the summary observation.
                traces = lf.api.trace.list(session_id=session_id, limit=20)
                summary_output: dict | None = None
                for trace in (traces.data or []):
                    obs = lf.api.observations.get_many(
                        trace_id=trace.id,
                        name="session_summary_generation",
                        limit=1,
                    )
                    if obs.data:
                        summary_output = obs.data[0].output or {}
                        break

                if summary_output is None:
                    failures.append(
                        f"{label} summary: no session_summary_generation observation "
                        "found in Langfuse"
                    )
                    continue

                if not summary_output.get("exercise_type"):
                    failures.append(f"{label} summary: exercise_type is null")
                rep_count = summary_output.get("rep_count")
                if rep_count is None or rep_count <= 0:
                    failures.append(f"{label} summary: rep_count is 0 or null")
            except Exception as exc:
                failures.append(f"{label} Langfuse query error: {exc}")
    except Exception as exc:
        failures.append(f"Langfuse client init failed: {exc}")
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

    # Flush traces before querying Langfuse for summary checks
    print("\nFlushing Langfuse traces ...", end="  ", flush=True)
    _langfuse.flush()
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

    total_failures = ws_assert_failed + ws_errored + len(lf_failures)
    print(f"\n{'ALL CHECKS PASSED' if total_failures == 0 else f'{total_failures} check(s) failed — see above'}")
    print("Check https://us.cloud.langfuse.com for full traces.")


if __name__ == "__main__":
    asyncio.run(main())
