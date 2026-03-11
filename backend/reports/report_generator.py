"""Generate human-readable session summaries from Firestore."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

try:
    from google.cloud import firestore
except Exception:  # pragma: no cover
    firestore = None

from backend.firestore.schema import SESSION_SUMMARIES_COLLECTION, SessionSummary

try:
    from google import genai
except Exception:  # pragma: no cover
    genai = None


class SessionReportGenerator:
    def __init__(self, client: "firestore.Client | None"):
        self._client = client
        self._genai_client = None
        if genai is not None:
            try:
                self._genai_client = genai.Client(
                    vertexai=os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() == "true",
                    project=os.getenv("GOOGLE_CLOUD_PROJECT", "chaos-fit"),
                    location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
                )
            except Exception:
                self._genai_client = None

    def fetch_summary(self, session_id: str) -> SessionSummary | None:
        if not self._client:
            return None
        doc = self._client.collection(SESSION_SUMMARIES_COLLECTION).document(session_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        return SessionSummary.from_dict(data)

    def generate_text_report(self, session_id: str) -> str | None:
        summary = self.fetch_summary(session_id)
        if not summary:
            return None
        return self.format_summary(summary)

    def format_summary(self, summary: SessionSummary) -> str:
        lines: list[str] = []
        user_label = summary.user_id or "parent"
        lines.append(
            f"Session {summary.session_id} for {user_label} started at {summary.started_at} and ended at {summary.ended_at}."
        )
        exercise_focus = summary.exercise_type or "general coaching"
        reps_text = str(summary.rep_count) if summary.rep_count is not None else "TBD"
        lines.append(f"Exercise focus: {exercise_focus}. Reps logged: {reps_text}.")
        lines.append(f"Interruptions captured: {summary.interruption_count}.")
        if summary.session_goal:
            lines.append(f"Session goal: {summary.session_goal}.")
        if summary.form_corrections:
            lines.append("Form corrections observed:")
            for correction in summary.form_corrections:
                lines.append(f"  - {correction}")
        lines.append(f"Recorded at {summary.created_at}.")
        return "\n".join(lines)

    @staticmethod
    def _parse_iso(ts: str | None) -> datetime | None:
        if not ts:
            return None
        try:
            normalized = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except Exception:
            return None

    def _duration_seconds(self, summary: SessionSummary) -> int | None:
        started = self._parse_iso(summary.started_at)
        ended = self._parse_iso(summary.ended_at)
        if not started or not ended:
            return None
        delta = ended - started
        seconds = int(delta.total_seconds())
        return max(seconds, 0)

    def _generate_gemini_summary(self, summary: SessionSummary, duration_sec: int | None) -> dict[str, str] | None:
        if self._genai_client is None:
            return None

        model = os.getenv("SUMMARY_MODEL", "gemini-2.5-flash")
        exercise = summary.exercise_type or "workout"
        rep_count = summary.rep_count if summary.rep_count is not None else 0
        interruptions = summary.interruption_count
        corrections = list(summary.form_corrections or ())
        goal = summary.session_goal or ""

        duration_text = f"{duration_sec} seconds" if duration_sec is not None else "unknown duration"

        prompt = (
            "You are an intense but supportive CrossFit coach writing a post-workout recap. "
            "Write in a crisp, earned tone (no fluff).\n\n"
            "Return STRICT JSON with exactly these keys:\n"
            "- summary_text: a single paragraph recap of what the athlete did\n"
            "- motivational_closing_line: one short, punchy closing line (board-signoff style)\n\n"
            "Session data:\n"
            f"- exercise_type: {exercise}\n"
            f"- rep_count: {rep_count}\n"
            f"- form_corrections: {corrections}\n"
            f"- interruption_count: {interruptions}\n"
            f"- duration: {duration_text}\n"
            f"- session_goal: {goal}\n"
        )

        try:
            response = self._genai_client.models.generate_content(
                model=model,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            text = getattr(response, "text", None)
            if not text:
                return None
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return None
            summary_text = parsed.get("summary_text")
            closing = parsed.get("motivational_closing_line")
            if not isinstance(summary_text, str) or not isinstance(closing, str):
                return None
            summary_text = summary_text.strip()
            closing = closing.strip()
            if not summary_text or not closing:
                return None
            return {"summary_text": summary_text, "motivational_closing_line": closing}
        except Exception:
            return None

    def to_payload(self, session_id: str) -> dict[str, Any] | None:
        summary = self.fetch_summary(session_id)
        if not summary:
            return None

        duration_sec = self._duration_seconds(summary)
        gemini_bits = self._generate_gemini_summary(summary, duration_sec=duration_sec) or {}
        summary_text = gemini_bits.get("summary_text") or self.format_summary(summary)
        motivational_closing_line = gemini_bits.get("motivational_closing_line") or "Good work. Show up tomorrow."

        return {
            "session_id": summary.session_id,
            "user_id": summary.user_id,
            "text_report": self.format_summary(summary),
            "details": summary.to_dict(),
            "summary_text": summary_text,
            "motivational_closing_line": motivational_closing_line,
            "rep_count": summary.rep_count,
            "exercise_type": summary.exercise_type,
            "form_corrections": list(summary.form_corrections),
            "interruption_count": summary.interruption_count,
            "session_duration_sec": duration_sec,
            "started_at": summary.started_at,
            "ended_at": summary.ended_at,
        }
