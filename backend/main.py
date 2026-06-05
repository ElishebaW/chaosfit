"""FastAPI app using ADK bidi-demo websocket pattern for ChaosFit live coaching."""
# ruff: noqa: E402  — load_dotenv must run before any Langfuse/ADK import

from __future__ import annotations

# load_dotenv must run before any Langfuse import — the SDK initializes its
# global singleton on first module import and won't pick up env vars added later.
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import asyncio
import base64
import binascii
import json
import logging
import time
import warnings
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from langfuse import Langfuse, get_client, observe, propagate_attributes
from opentelemetry import trace as _otel_trace
from opentelemetry.sdk.trace import SpanProcessor as _SpanProcessor
from opentelemetry.trace import Status as _OtelStatus, StatusCode as _OtelStatusCode
from starlette.websockets import WebSocketState

from backend.coach_agent.agent import agent, coach_prompt
from backend.live_agent.session_manager import SessionManager
from backend.reports.report_generator import SessionReportGenerator
from backend.session_utils import extract_end_summary, normalize_corrections, safe_int, safe_str


class _SuppressWebSocketCloseErrorProcessor(_SpanProcessor):
    """Clears ERROR status on spans where Gemini SDK reported a normal WebSocket close.

    The Gemini live SDK converts ConnectionClosedOK (code 1000) to APIError,
    which OTel records as ERROR. Sessions that ended via the 'end' event are
    successful — mark them OK so Langfuse doesn't flag them as failures.
    """
    def on_start(self, span, parent_context=None): pass
    def on_end(self, span) -> None:
        if (span.status.status_code == _OtelStatusCode.ERROR
                and span.status.description
                and "1000 None" in span.status.description):
            span._status = _OtelStatus(_OtelStatusCode.OK)  # noqa: SLF001
    def shutdown(self) -> None: pass
    def force_flush(self, timeout_millis: int = 30000) -> bool: return True


# Register BEFORE Langfuse() so this processor runs first in on_end.
_otel_provider = _otel_trace.get_tracer_provider()
if hasattr(_otel_provider, "add_span_processor"):
    _otel_provider.add_span_processor(_SuppressWebSocketCloseErrorProcessor())

_langfuse = Langfuse()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

APP_NAME = "chaosfit"

app = FastAPI(title="ChaosFit ADK Bidi API")
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
session_manager = SessionManager()


@observe(name="gemini_live_coach_turn", as_type="generation")
def _trace_coach_turn(event_type: str, session_id: str, user_id: str, interrupted: bool, model: str) -> dict[str, Any]:
    with propagate_attributes(session_id=session_id, user_id=user_id):
        get_client().update_current_generation(model=model, prompt=coach_prompt)
        return {"event_type": event_type, "session_id": session_id, "interrupted": interrupted}


_safe_int = safe_int
_safe_str = safe_str
_normalize_corrections = normalize_corrections


def _compile_resume_context(context: dict[str, Any]) -> str:
    exercise = context.get("current_exercise") or "the exercise"
    reps = context.get("reps_this_set", 0)
    remaining = context.get("time_remaining_sec")
    elapsed = int(context.get("elapsed_active_sec", 0))
    pause_count = context.get("pause_count", 0)
    last_correction = context.get("last_correction")

    if remaining is not None:
        mins, secs = divmod(remaining, 60)
        time_context = f"{mins}m {secs}s remaining" if mins else f"{secs}s remaining"
    else:
        mins = elapsed // 60
        time_context = f"~{mins} minute{'s' if mins != 1 else ''} in" if mins else "just started"

    try:
        prompt_obj = _langfuse.get_prompt("coach-resume-context", label="production")
        return prompt_obj.compile(
            current_exercise=str(exercise),
            reps_this_set=str(reps),
            total_reps=str(context.get("total_reps", 0)),
            time_context=time_context,
            pause_count=str(pause_count),
            last_correction=str(last_correction) if last_correction else "none",
        )
    except Exception:
        return (
            f"Session resumed. You were doing {exercise} — {reps} reps in this set. "
            f"{time_context.capitalize()}. Continue coaching from where you left off."
        )


async def _process_coach_tool_event(event: Any, session_id: str, session_manager: SessionManager) -> dict | None:
    """Process coach tool responses for exercise data and fatigue events.

    Returns a dict to forward to the WebSocket client (e.g. routine_plan_updated), or None.
    """
    try:
        if not (hasattr(event, 'tool_response') and event.tool_response is not None):
            return None
        response_data = event.tool_response
        if not (isinstance(response_data, dict) and response_data.get("status") == "success"):
            return None

        response_type = response_data.get("type")

        if response_type == "fatigue_update":
            payload = {**response_data, "session_id": session_id}
            session_manager.append_event(session_id=session_id, event_type="fatigue_update", payload=payload)
            logger.info("Processed fatigue_update for session %s level=%.2f confidence=%s",
                        session_id, payload.get("fatigue_level", 0), payload.get("confidence"))
            return None

        if response_type == "difficulty_adjustment":
            payload = {**response_data, "session_id": session_id}
            prev_ts = session_manager.get(session_id).last_difficulty_adjustment_at
            session_manager.append_event(session_id=session_id, event_type="difficulty_adjustment", payload=payload)
            state = session_manager.get(session_id)
            logger.info("Processed difficulty_adjustment for session %s direction=%s",
                        session_id, response_data.get("direction"))
            if state.last_difficulty_adjustment_at != prev_ts and state.routine_plan:
                return {"type": "routine_plan_updated", "routine_plan": state.routine_plan}
            return None

        # emit_exercise_data response — event dict is nested under "event" key
        event_data = response_data.get("event")
        if event_data and isinstance(event_data, dict):
            tool_session_id = event_data.get("session_id")
            event_data["session_id"] = session_id
            session_manager.append_event(session_id=session_id, event_type="exercise_update", payload=event_data)
            logger.info(f"Processed coach exercise event for session {session_id}: {event_data}")
            if tool_session_id and tool_session_id != session_id:
                logger.warning(f"Session ID mismatch - tool: {tool_session_id}, actual: {session_id} - corrected")
            if event_data.get("interruption"):
                logger.info(f"Coach tool interruption flag set for session {session_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to process coach tool event: {e}")
        return None


_extract_end_summary = extract_end_summary

@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/summary")
async def summary_page() -> FileResponse:
    return FileResponse(static_dir / "summary.html")


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/reports/session/{session_id}")
async def session_report(session_id: str) -> dict[str, Any]:
    client = session_manager.get_firestore_client()
    if not client:
        raise HTTPException(status_code=503, detail="Firestore is not configured")
    report = SessionReportGenerator(client).to_payload(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Session summary not found")
    return report


@app.post("/test-exercise-event/{session_id}")
async def send_test_exercise_event(session_id: str):
    """Test endpoint to simulate exercise data events"""
    try:
        # Simulate an exercise update event
        session_manager.append_event(
            session_id=session_id,
            event_type="exercise_update",
            payload={
                "exercise_id": "push_ups",
                "rep_count": 5,
                "form_corrections": ["keep back straight", "lower chest more"],
                "exercise_type": "strength_training"
            }
        )
        return {"status": "success", "message": f"Test exercise data sent to session {session_id}"}
    except KeyError:
        return {"status": "error", "message": f"Session {session_id} not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/test-end-event/{session_id}")
async def send_test_end_event(session_id: str):
    """Test endpoint to simulate proper session end"""
    try:
        session_manager.complete_session(session_id)
        session_manager.record_session_summary(
            session_id=session_id,
            user_id="demo-user",
            exercise_type="push_ups",
            rep_count=25,
            user_speech_interruptions=0,
            form_corrections=["keep back straight", "lower chest more"],
            session_goal="improve push-up form"
        )
        return {"status": "success", "message": f"Test end event sent to session {session_id}"}
    except KeyError:
        return {"status": "error", "message": f"Session {session_id} not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
    proactivity: bool = False,
    affective_dialog: bool = False,
) -> None:
    await websocket.accept()

    async def safe_send_text(payload: str) -> None:
        if websocket.application_state != WebSocketState.CONNECTED:
            return
        try:
            await websocket.send_text(payload)
        except (WebSocketDisconnect, RuntimeError):
            return

    model_name = str(agent.model)
    # Covers both old preview naming (native-audio-*) and GA live naming (*-live-*)
    is_audio_capable = "native-audio" in model_name.lower() or "-live-" in model_name.lower()

    if is_audio_capable:
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            session_resumption=types.SessionResumptionConfig(),
            proactivity=(
                types.ProactivityConfig(proactive_audio=True) if proactivity else None
            ),
            enable_affective_dialog=affective_dialog if affective_dialog else None,
        )
    else:
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["TEXT"],
            input_audio_transcription=None,
            output_audio_transcription=None,
            session_resumption=types.SessionResumptionConfig(),
        )

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    try:
        session_manager.start_session(
            session_id=session_id,
            parent_id=user_id,
            time_remaining_sec=None,
            live_model=str(agent.model),
        )
    except Exception:
        logger.exception("Failed to initialize session manager state; continuing without persistence")

    live_request_queue = LiveRequestQueue()
    user_speech_interruptions = 0

    async def send_session_state(status: str, reason: str | None = None) -> None:
        payload: dict[str, str] = {"type": "session_state", "status": status}
        if reason:
            payload["reason"] = reason
        await safe_send_text(json.dumps(payload))

    async def upstream_task() -> None:
        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    logging.info(f"WebSocket disconnected for session {session_id}, cleaning up session")
                    try:
                        state = session_manager.get(session_id)
                        logging.info(f"Session {session_id} status: {state.status}, exercise_type: {state.current_exercise}, reps: {state.cumulative_rep_count}, pauses: {state.pause_count}, user_speech_interruptions: {user_speech_interruptions}")
                        
                        # Only save summary if session wasn't already properly ended
                        if state.status != "ended":
                            session_manager.complete_session(session_id)
                            # Use tracked exercise data for disconnected sessions
                            session_manager.record_session_summary(
                                session_id=session_id,
                                user_id=user_id,
                                exercise_type=state.current_exercise or "unknown",
                                rep_count=state.cumulative_rep_count,
                                user_speech_interruptions=user_speech_interruptions,
                                form_corrections=state.form_corrections,
                                session_goal="session disconnected"
                            )
                            logging.info(f"Session {session_id} cleaned up on disconnect with exercise data")
                        else:
                            logging.info(f"Session {session_id} already ended, skipping disconnect summary")
                    except Exception as e:
                        logging.error(f"Failed to cleanup session {session_id}: {e}")
                        logging.exception("Full exception details:", exc_info=True)
                    return

                if "bytes" in message and message["bytes"] is not None:
                    logger.debug("binary_audio size_bytes=%d session_id=%s", len(message["bytes"]), session_id)
                    if not session_manager.can_accept_media(session_id):
                        continue
                    audio_blob = types.Blob(
                        mime_type="audio/pcm;rate=16000",
                        data=message["bytes"],
                    )
                    live_request_queue.send_realtime(audio_blob)
                    continue

                if "text" not in message or message["text"] is None:
                    continue

                text = message["text"]
                payload = json.loads(text)
                logging.info(f"Received event: {payload.get('type')} with payload keys: {list(payload.keys())}")
                
                # Check for exercise data in payload
                exercise_keys = ['exercise_id', 'rep_count', 'form_corrections', 'exercise_type']
                found_exercise_data = [key for key in exercise_keys if key in payload]
                if found_exercise_data:
                    logging.info(f"Exercise update received: {found_exercise_data}")
                    
                event_type = payload.get("type")
                if event_type is None:
                    logging.warning("Missing event type in payload")
                    continue

                if event_type == "pause":
                    reason = str(payload.get("reason", "manual_pause"))
                    session_manager.pause_session(session_id, reason=reason)
                    await send_session_state("paused", reason=reason)
                    continue

                if event_type == "resume":
                    session_manager.resume_session(session_id)
                    rescheduled = session_manager.maybe_reschedule(session_id, trigger="resume")
                    await send_session_state("resumed")
                    state = session_manager.get(session_id)
                    if rescheduled:
                        await safe_send_text(json.dumps({
                            "type": "routine_plan_updated",
                            "routine_plan": state.routine_plan,
                        }))
                        blocks_remaining = len((state.routine_plan or {}).get("blocks") or [])
                        live_request_queue.send_content(types.Content(parts=[types.Part(
                            text=f"Schedule updated: {blocks_remaining} blocks remaining. Continue from the current exercise."
                        )]))
                    resume_text = _compile_resume_context(state.contextual_resume_summary())
                    live_request_queue.send_content(
                        types.Content(parts=[types.Part(text=resume_text)])
                    )
                    continue

                if event_type == "block_end":
                    session_manager.advance_block(session_id)
                    rescheduled = session_manager.maybe_reschedule(session_id, trigger="block-end")
                    if rescheduled:
                        state = session_manager.get(session_id)
                        await safe_send_text(json.dumps({
                            "type": "routine_plan_updated",
                            "routine_plan": state.routine_plan,
                        }))
                        blocks_remaining = len((state.routine_plan or {}).get("blocks") or [])
                        live_request_queue.send_content(types.Content(parts=[types.Part(
                            text=f"Schedule updated: {blocks_remaining} blocks remaining. Continue from the current exercise."
                        )]))
                    continue

                if event_type == "ping":
                    await safe_send_text(json.dumps({
                        "type": "pong",
                        "sentAt": payload.get("sentAt"),
                    }))
                    continue

                if event_type == "exercise_update":
                    # Process exercise update events from coach tool
                    session_manager.append_event(
                        session_id=session_id,
                        event_type="exercise_update",
                        payload=payload
                    )
                    logging.info(f"Processed exercise update for session {session_id}: {found_exercise_data}")
                    continue

                if event_type == "end":
                    logging.info(f"Processing end event for session {session_id}")
                    summary_payload = _extract_end_summary(payload)
                    logging.info(f"Session summary extracted: exercise_type={summary_payload.get('exercise_type')}, reps={summary_payload.get('rep_count')}")
                    
                    session_manager.complete_session(session_id)
                    logging.info("Session completed, calling record_session_summary")
                    
                    # Get current state for accurate data
                    state = session_manager.get(session_id)
                    logging.info(f"Session state before summary: exercise={state.current_exercise}, reps={state.cumulative_rep_count}, pauses={state.pause_count}, user_speech_interruptions={user_speech_interruptions}, corrections={len(state.form_corrections)}")
                    logging.info(f"form_corrections at summary time: {state.form_corrections}")
                    
                    # Use accumulated state data as primary source, fallback to extracted data
                    session_manager.record_session_summary(
                        session_id,
                        user_id=user_id,
                        exercise_type=state.current_exercise or summary_payload["exercise_type"],
                        rep_count=state.cumulative_rep_count if state.cumulative_rep_count > 0 else summary_payload["rep_count"],
                        user_speech_interruptions=user_speech_interruptions,
                        form_corrections=state.form_corrections if state.form_corrections else summary_payload["form_corrections"],
                        session_goal=summary_payload["session_goal"] or "coach-guided session",
                    )
                    logging.info("Session summary recorded")
                    get_client().flush()

                    await send_session_state("ended")
                    live_request_queue.close()
                    return

                if not session_manager.can_accept_media(session_id):
                    continue

                if event_type == "text":
                    content = types.Content(parts=[types.Part(text=str(payload.get("text", "")))])
                    live_request_queue.send_content(content)
                    continue

                if event_type in {"image", "video"}:
                    captured_at = payload.get("capturedAt")
                    age_ms = None
                    if captured_at is not None:
                        age_ms = time.time() * 1000 - float(captured_at)
                        if age_ms > 3000:
                            logger.warning(
                                "Dropping stale %s frame age_ms=%.0f session_id=%s",
                                event_type, age_ms, session_id,
                            )
                            continue
                    try:
                        raw = base64.b64decode(payload.get("data", ""), validate=True)
                    except (binascii.Error, ValueError):
                        logger.warning(
                            "Skipping malformed %s frame for session_id=%s", event_type, session_id
                        )
                        continue
                    mime_type = payload.get("mimeType") or payload.get("mime_type") or "image/jpeg"
                    logger.debug("media_frame event_type=%s age_ms=%s size_bytes=%d session_id=%s", event_type, f"{age_ms:.0f}" if age_ms is not None else "n/a", len(raw), session_id)
                    media_blob = types.Blob(mime_type=mime_type, data=raw)
                    live_request_queue.send_realtime(media_blob)
                    continue

                if event_type == "audio":
                    try:
                        raw = base64.b64decode(payload.get("data", ""), validate=True)
                    except (binascii.Error, ValueError):
                        logger.warning("Skipping malformed audio chunk for session_id=%s", session_id)
                        continue
                    mime_type = payload.get("mimeType") or payload.get("mime_type") or "audio/pcm;rate=16000"
                    audio_blob = types.Blob(mime_type=mime_type, data=raw)
                    live_request_queue.send_realtime(audio_blob)
                    continue
        except WebSocketDisconnect:
            return

    async def downstream_task() -> None:
        nonlocal user_speech_interruptions
        try:
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                if websocket.application_state != WebSocketState.CONNECTED:
                    return
                
                # Debug: log event type for troubleshooting
                event_type = type(event).__name__
                if event_type not in ['ContentUpdateEvent', 'TurnCompleteEvent']:
                    logger.debug(f"Received event type: {event_type}")
                
                # Handle coach tool responses for exercise data
                if hasattr(event, 'tool_response') and event.tool_response is not None:
                    logger.info(f"Coach tool response detected: {event.tool_response}")
                    plan_update = await _process_coach_tool_event(event, session_id, session_manager)
                    if plan_update:
                        await safe_send_text(json.dumps(plan_update))
                else:
                    # Debug: check if event has any tool-related attributes
                    tool_attrs = {k: v for k, v in event.__dict__.items() if 'tool' in k.lower()}
                    if tool_attrs:
                        logger.debug(f"Event has tool attributes: {tool_attrs}")
                
                interrupted = bool(getattr(event, "interrupted", False))
                _trace_coach_turn(type(event).__name__, session_id, user_id, interrupted, str(agent.model))
                if interrupted:
                    user_speech_interruptions += 1
                    logger.info(
                        "Interruption event session_id=%s user_id=%s user_speech_interruptions=%s",
                        session_id,
                        user_id,
                        user_speech_interruptions,
                    )
                await safe_send_text(event.model_dump_json(exclude_none=True, by_alias=True))
        except WebSocketDisconnect:
            return
        except Exception as exc:
            # Check if this is an expected ADK connection error after end event
            error_str = str(exc)
            is_expected_error = (
                "1000 None" in error_str or  # Normal connection close
                ("1007 None" in error_str and "Request contains an invalid argument" in error_str)  # Expected after end event
            )
            
            if is_expected_error:
                logger.info(
                    "Live runner ended normally after end event session_id=%s user_id=%s error=%s",
                    session_id,
                    user_id,
                    exc,
                )
            else:
                logger.warning(
                    "Live runner ended unexpectedly session_id=%s user_id=%s error=%s",
                    session_id,
                    user_id,
                    exc,
                )
            
            # Clean up session on unexpected termination only if not already ended
            try:
                state = session_manager.get(session_id)
                # Only save summary if session wasn't already properly ended AND this wasn't an expected error
                if state.status != "ended" and not is_expected_error:
                    session_manager.complete_session(session_id)
                    session_manager.record_session_summary(
                        session_id=session_id,
                        user_id=user_id,
                        exercise_type=state.current_exercise or "unknown",
                        rep_count=state.cumulative_rep_count,
                        user_speech_interruptions=user_speech_interruptions,
                        form_corrections=state.form_corrections,
                        session_goal="session terminated unexpectedly"
                    )
                    logger.info(f"Session {session_id} cleaned up after unexpected termination with exercise data")
                else:
                    if is_expected_error:
                        logger.info(f"Session {session_id} ended normally, expected ADK error suppressed")
                    else:
                        logger.info(f"Session {session_id} already ended, skipping unexpected termination summary")
            except Exception as cleanup_exc:
                logger.error(f"Failed to cleanup session {session_id}: {cleanup_exc}")
            return

    try:
        await send_session_state("active")
        upstream = asyncio.create_task(upstream_task())
        downstream = asyncio.create_task(downstream_task())
        done, pending = await asyncio.wait(
            {upstream, downstream}, return_when=asyncio.FIRST_EXCEPTION
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            exc = task.exception()
            if exc:
                raise exc
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected user_id=%s session_id=%s", user_id, session_id)
    except Exception:
        logger.exception("Unexpected websocket failure")
    finally:
        try:
            session_manager.complete_session(session_id)
        except Exception:
            pass
        live_request_queue.close()
