"""FastAPI app using ADK bidi-demo websocket pattern for ChaosFit live coaching."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import os
import warnings
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from backend.live_agent.session_manager import SessionManager
from backend.reports.report_generator import SessionReportGenerator

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from backend.coach_agent.agent import agent  # noqa: E402  pylint: disable=wrong-import-position

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


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalize_corrections(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            entry = _safe_str(item)
            if entry:
                out.append(entry)
        return out
    single = _safe_str(value)
    return [single] if single else []


async def _process_coach_tool_event(event: Any, session_id: str, session_manager: SessionManager) -> None:
    """Process coach tool responses for exercise data events."""
    try:
        # Check if this is an exercise data tool response
        if hasattr(event, 'tool_response') and event.tool_response is not None:
            response_data = event.tool_response
            
            # Parse the tool response to extract exercise event data
            if isinstance(response_data, dict) and response_data.get("status") == "success":
                event_data = response_data.get("event")
                if event_data and isinstance(event_data, dict):
                    # Always override with the correct session_id from the WebSocket context
                    tool_session_id = event_data.get("session_id")
                    event_data["session_id"] = session_id  # Override with actual session ID
                    
                    # Create exercise_update event for session manager
                    session_manager.append_event(
                        session_id=session_id,
                        event_type="exercise_update",
                        payload=event_data
                    )
                    logger.info(f"Processed coach exercise event for session {session_id}: {event_data}")
                    
                    # Log session ID mapping for debugging
                    if tool_session_id and tool_session_id != session_id:
                        logger.warning(f"Session ID mismatch - tool: {tool_session_id}, actual: {session_id} - corrected")
                    
                    # Update interruption count if this was an interruption
                    if event_data.get("interruption"):
                        # This will be handled by the existing interrupted_count logic
                        logger.info(f"Coach interruption detected for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to process coach tool event: {e}")


def _extract_end_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary_block = payload.get("summary")
    if not isinstance(summary_block, dict):
        summary_block = {}
    exercise_type = _safe_str(summary_block.get("exercise_type") or payload.get("exercise_type"))
    rep_count = _safe_int(summary_block.get("rep_count") or payload.get("rep_count"))
    session_goal = _safe_str(summary_block.get("session_goal") or payload.get("session_goal"))
    corrections = _normalize_corrections(
        summary_block.get("form_corrections") or payload.get("form_corrections")
    )
    return {
        "exercise_type": exercise_type,
        "rep_count": rep_count,
        "session_goal": session_goal,
        "form_corrections": corrections,
    }

@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(static_dir / "index.html")


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
            interruption_count=2,
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
    is_native_audio = "native-audio" in model_name.lower()

    if is_native_audio:
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
    interrupted_count = 0

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
                        logging.info(f"Session {session_id} status: {state.status}, exercise_type: {state.current_exercise}, reps: {state.cumulative_rep_count}, interruptions: {state.total_interruptions}")
                        
                        # Only save summary if session wasn't already properly ended
                        if state.status != "ended":
                            session_manager.complete_session(session_id)
                            # Use tracked exercise data for disconnected sessions
                            session_manager.record_session_summary(
                                session_id=session_id,
                                user_id=user_id,
                                exercise_type=state.current_exercise or "unknown",
                                rep_count=state.cumulative_rep_count,
                                interruption_count=interrupted_count + state.coach_interruptions,
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

                payload = json.loads(message["text"])
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
                    await send_session_state("resumed")
                    continue

                if event_type == "end":
                    logging.info(f"Processing end event for session {session_id}")
                    summary_payload = _extract_end_summary(payload)
                    logging.info(f"Session summary extracted: exercise_type={summary_payload.get('exercise_type')}, reps={summary_payload.get('rep_count')}")
                    
                    session_manager.complete_session(session_id)
                    logging.info("Session completed, calling record_session_summary")
                    
                    # Get current state for accurate data
                    state = session_manager.get(session_id)
                    logging.info(f"Session state before summary: exercise={state.current_exercise}, reps={state.cumulative_rep_count}, interruptions={state.total_interruptions}, corrections={len(state.form_corrections)}")
                    
                    # Use accumulated state data as primary source, fallback to extracted data
                    session_manager.record_session_summary(
                        session_id,
                        user_id=user_id,
                        exercise_type=state.current_exercise or summary_payload["exercise_type"],
                        rep_count=state.cumulative_rep_count if state.cumulative_rep_count > 0 else summary_payload["rep_count"],
                        interruption_count=interrupted_count + state.coach_interruptions,
                        form_corrections=state.form_corrections if state.form_corrections else summary_payload["form_corrections"],
                        session_goal=summary_payload["session_goal"] or "coach-guided session",
                    )
                    logging.info("Session summary recorded")

                    # Session summary is already written by session_manager.record_session_summary()
                    # No need for separate async call
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
                    try:
                        raw = base64.b64decode(payload.get("data", ""), validate=True)
                    except (binascii.Error, ValueError):
                        logger.warning(
                            "Skipping malformed %s frame for session_id=%s", event_type, session_id
                        )
                        continue
                    mime_type = payload.get("mimeType") or payload.get("mime_type") or "image/jpeg"
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
        nonlocal interrupted_count
        try:
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                if websocket.application_state != WebSocketState.CONNECTED:
                    return
                
                # Handle coach tool responses for exercise data
                if hasattr(event, 'tool_response') and event.tool_response is not None:
                    await _process_coach_tool_event(event, session_id, session_manager)
                
                if bool(getattr(event, "interrupted", False)):
                    interrupted_count += 1
                    logger.info(
                        "Interruption event session_id=%s user_id=%s interrupted_count=%s",
                        session_id,
                        user_id,
                        interrupted_count,
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
                        interruption_count=interrupted_count + state.coach_interruptions,
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
