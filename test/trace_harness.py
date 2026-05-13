#!/usr/bin/env python3
"""
Trace harness — Phase 1 Group 3.

Drives WebSocket sessions against the running server to generate LangSmith trace data.
This is NOT a CI test. Run it manually to collect traces.

Usage:
    # Against local server (start with: uv run uvicorn backend.main:app --port 8080)
    python test/trace_harness.py

    # Against the deployed Cloud Run URL
    CHAOSFIT_WS_URL=wss://your-cloud-run-url python test/trace_harness.py

    # Single scenario, 3 runs
    python test/trace_harness.py --scenario session_with_interruption --runs 3

Scenarios:
    clean_session           — normal session, 5 frames, one exercise, clean end
    session_with_interruption — pause mid-session, resume, then end
    misidentified_exercise  — exercise_update claims a different exercise than context implies
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
from langsmith import traceable

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
    Exercise mismatch: frames are sent but the exercise_update reports 'lunge'
    while the prior context implied 'squat'. Surfaces detection inconsistency in traces.
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

    return {
        "scenario": scenario,
        "run_index": run_index,
        "session_id": session_id,
        "events_received": len(received),
        "event_types": [m.get("type") for m in received],
        "error": error,
    }


@traceable(name="trace_harness_scenario", run_type="chain")
async def _traced_scenario(base_url: str, scenario: str, run_index: int) -> dict[str, Any]:
    """Parent LangSmith span — session_id links client run to server-side pipeline traces."""
    return await _run_scenario(base_url, scenario, run_index)


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
        else:
            print(f"OK — {result['events_received']} events, session={result['session_id']}")

    passed = sum(1 for r in results if not r["error"])
    print(f"\n{passed}/{len(results)} runs succeeded.")
    if passed < len(results):
        print("\nFailed runs:")
        for r in results:
            if r["error"]:
                print(f"  [{r['scenario']} #{r['run_index']}] {r['error']}")

    print("\nCheck https://smith.langsmith.com for traces tagged 'trace_harness_scenario'.")


if __name__ == "__main__":
    asyncio.run(main())
