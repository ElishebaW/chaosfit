"""FastAPI app using ADK bidi-demo websocket pattern for ChaosFit live coaching."""

from __future__ import annotations

import asyncio
import binascii
import base64
import json
import logging
import warnings
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

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


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
    proactivity: bool = False,
    affective_dialog: bool = False,
) -> None:
    await websocket.accept()

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

    live_request_queue = LiveRequestQueue()
    interrupted_count = 0

    async def upstream_task() -> None:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return

            if "bytes" in message and message["bytes"] is not None:
                audio_blob = types.Blob(
                    mime_type="audio/pcm;rate=16000",
                    data=message["bytes"],
                )
                live_request_queue.send_realtime(audio_blob)
                continue

            if "text" not in message or message["text"] is None:
                continue

            payload = json.loads(message["text"])
            event_type = payload.get("type")

            if event_type == "text":
                content = types.Content(parts=[types.Part(text=str(payload.get("text", "")))])
                live_request_queue.send_content(content)
                continue

            if event_type in {"image", "video"}:
                try:
                    raw = base64.b64decode(payload.get("data", ""), validate=True)
                except (binascii.Error, ValueError):
                    logger.warning("Skipping malformed %s frame for session_id=%s", event_type, session_id)
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

            if event_type == "end":
                return

    async def downstream_task() -> None:
        nonlocal interrupted_count
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config,
        ):
            if bool(getattr(event, "interrupted", False)):
                interrupted_count += 1
                logger.info(
                    "Interruption event session_id=%s user_id=%s interrupted_count=%s",
                    session_id,
                    user_id,
                    interrupted_count,
                )
            await websocket.send_text(event.model_dump_json(exclude_none=True, by_alias=True))

    try:
        await asyncio.gather(upstream_task(), downstream_task())
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected user_id=%s session_id=%s", user_id, session_id)
    except Exception:
        logger.exception("Unexpected websocket failure")
    finally:
        live_request_queue.close()
