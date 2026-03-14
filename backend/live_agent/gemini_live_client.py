"""Gemini Live bidirectional client for realtime ChaosFit coaching."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from .form_feedback_prompt import build_live_system_instruction


PREFERRED_LIVE_MODELS = (
    "gemini-live-2.5-flash-preview",
    "gemini-2.0-flash-live-001",
    "gemini-2.0-flash-live-preview-04-09",
    "gemini-2.5-flash-preview-native-audio-dialog",
    "gemini-2.5-flash",
)


@dataclass(frozen=True)
class LiveClientConfig:
    model: str = "auto"
    project: str = "chaos-fit"
    location: str = "global"
    output_voice: str = "Aoede"


class GeminiLiveClient:
    """Owns one Live API session and bridges queue events to/from the model."""

    def __init__(self, config: LiveClientConfig | None = None) -> None:
        cfg = config or LiveClientConfig(
            model=os.getenv("LIVE_MODEL", "auto"),
            project=os.getenv("GOOGLE_CLOUD_PROJECT", "chaos-fit"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
            output_voice=os.getenv("LIVE_OUTPUT_VOICE", "Aoede"),
        )
        self.config = cfg
        self.client = genai.Client(
            vertexai=os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() == "true",
            project=cfg.project,
            location=cfg.location,
        )

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        return name.removeprefix("models/")

    @staticmethod
    def _supports_bidi(model_obj: Any) -> bool:
        for attr in ("supported_actions", "supported_generation_methods"):
            values = getattr(model_obj, attr, None) or []
            for value in values:
                if "bidi" in str(value).lower() or "bidigeneratecontent" in str(value).lower():
                    return True
        return False

    def _list_live_models(self) -> list[str]:
        out: list[str] = []
        for m in self.client.models.list():
            name = self._normalize_model_name(getattr(m, "name", ""))
            if not name:
                continue
            if self._supports_bidi(m):
                out.append(name)
        return sorted(set(out))

    def resolve_live_model(self) -> str:
        available = self._list_live_models()
        if not available:
            raise RuntimeError("No Live bidi models available for this project/key")

        requested = self._normalize_model_name(self.config.model)
        if requested and requested.lower() != "auto":
            if requested in available:
                return requested
            raise RuntimeError(
                f"Requested LIVE_MODEL '{requested}' not available for bidi. "
                f"Available: {', '.join(available)}"
            )

        for candidate in PREFERRED_LIVE_MODELS:
            if candidate in available:
                return candidate
        return available[0]

    async def stream_session(
        self,
        *,
        inbound_queue: "asyncio.Queue[dict[str, Any] | None]",
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        session_goal: str | None = None,
    ) -> None:
        model = self.resolve_live_model()
        
        # Truncate session goal to avoid 1008 policy violations
        goal = session_goal or "Coach bodyweight workouts safely in real time."
        if len(goal) > 100:
            goal = goal[:100] + "..."
        
        system_instruction = build_live_system_instruction(session_goal=goal)
        
        # Further truncate if instruction is too long for native audio model
        if "native-audio" in model.lower() and len(system_instruction) > 300:
            system_instruction = (
                "You are ChaosFit Coach. Provide short form feedback.\n"
                "Prioritize safety. Interrupt risky form with <= 12 words.\n"
                f"Goal: {goal}"
            )

        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": system_instruction,
            # Mirrors ADK guidance: transcription + native audio output for low-latency coaching.
            "realtime_input_config": {
                "automatic_activity_detection": {
                    "start_of_speech_sensitivity": "START_SENSITIVITY_LOW",
                    "end_of_speech_sensitivity": "END_SENSITIVITY_LOW",
                },
                "activity_handling": "START_OF_ACTIVITY_INTERRUPTS",
            },
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": self.config.output_voice,
                    }
                }
            },
        }

        await on_event({"type": "session_started", "model": model})
        
        # Log instruction length for debugging 1008 errors
        import logging
        logging.info(f"Live session starting with model {model}")
        logging.info(f"System instruction length: {len(system_instruction)} chars")
        if "native-audio" in model.lower():
            logging.warning(f"Using native audio model with truncated instruction to avoid 1008 errors")

        async with self.client.aio.live.connect(model=model, config=config) as session:
            receive_task = asyncio.create_task(self._receive_loop(session=session, on_event=on_event))
            send_task = asyncio.create_task(self._send_loop(session=session, inbound_queue=inbound_queue, on_event=on_event))
            done, pending = await asyncio.wait(
                {receive_task, send_task},
                return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in pending:
                task.cancel()
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc

        await on_event({"type": "session_ended"})

    async def _send_loop(
        self,
        *,
        session: Any,
        inbound_queue: "asyncio.Queue[dict[str, Any] | None]",
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        while True:
            item = await inbound_queue.get()
            if item is None:
                break

            event_type = item.get("type")
            if event_type == "text":
                await session.send_client_content(
                    turns=[{"role": "user", "parts": [{"text": str(item.get('text', ''))}]}],
                    turn_complete=True,
                )
                continue

            if event_type in {"audio", "video"}:
                b64_data = item.get("data", "")
                if not b64_data:
                    continue
                raw = base64.b64decode(b64_data)
                mime = item.get("mime_type") or ("audio/pcm;rate=16000" if event_type == "audio" else "image/jpeg")
                blob = types.Blob(data=raw, mime_type=mime)

                send_realtime = getattr(session, "send_realtime_input", None)
                if send_realtime is None:
                    raise RuntimeError("Live session missing send_realtime_input API")

                if event_type == "audio":
                    await send_realtime(audio=blob)
                else:
                    await send_realtime(video=blob)
                continue

            if event_type == "end":
                break

            await on_event({"type": "warning", "message": f"Ignoring unknown input event: {event_type}"})

    async def _receive_loop(
        self,
        *,
        session: Any,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        try:
            async for message in session.receive():
                server_content = getattr(message, "server_content", None)
                if not server_content:
                    continue

                interrupted = bool(getattr(server_content, "interrupted", False))

                input_transcript = self._extract_text(getattr(server_content, "input_transcription", None))
                if input_transcript:
                    await on_event({
                        "type": "user_transcript",
                        "text": input_transcript,
                    })

                output_transcript = self._extract_text(getattr(server_content, "output_transcription", None))
                if output_transcript:
                    await on_event({
                        "type": "model_transcript",
                        "text": output_transcript,
                    })

                model_turn = getattr(server_content, "model_turn", None)
                if model_turn:
                    for part in getattr(model_turn, "parts", []) or []:
                        text = getattr(part, "text", None)
                        if text:
                            await on_event(
                                {
                                    "type": "model_text",
                                    "text": text,
                                    "interrupt": interrupted or text.strip().upper().startswith("CORRECTION:"),
                                }
                            )

                        inline_data = getattr(part, "inline_data", None)
                        if inline_data and getattr(inline_data, "data", None):
                            await on_event(
                                {
                                    "type": "model_audio",
                                    "mime_type": getattr(inline_data, "mime_type", "audio/pcm;rate=24000"),
                                    "data": base64.b64encode(inline_data.data).decode("ascii"),
                                    "interrupt": interrupted,
                                }
                            )

                if interrupted:
                    await on_event({"type": "interrupted"})

                if getattr(server_content, "turn_complete", False):
                    await on_event({"type": "turn_complete"})
                    
        except Exception as e:
            # Handle 1008 policy violation errors gracefully
            if "1008" in str(e) or "policy violation" in str(e).lower():
                import logging
                logging.error(f"1008 policy violation error in receive loop: {e}")
                logging.error("This typically happens when the system instruction is too long for the native audio model")
                await on_event({
                    "type": "error", 
                    "message": "Live session ended due to content policy restrictions. Try using a shorter session goal."
                })
            else:
                # Re-raise other exceptions
                raise

    @staticmethod
    def _extract_text(obj: Any) -> str | None:
        if obj is None:
            return None
        text = getattr(obj, "text", None)
        if text:
            return str(text)
        if isinstance(obj, dict):
            t = obj.get("text")
            if t:
                return str(t)
        try:
            dumped = obj.model_dump() if hasattr(obj, "model_dump") else json.loads(json.dumps(obj))
            if isinstance(dumped, dict) and dumped.get("text"):
                return str(dumped["text"])
        except Exception:
            return None
        return None
