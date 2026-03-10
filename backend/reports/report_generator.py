"""Generate human-readable session summaries from Firestore."""

from __future__ import annotations

from typing import Any

try:
    from google.cloud import firestore
except Exception:  # pragma: no cover
    firestore = None

from backend.firestore.schema import SESSION_SUMMARIES_COLLECTION, SessionSummary


class SessionReportGenerator:
    def __init__(self, client: "firestore.Client | None"):
        self._client = client

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

    def to_payload(self, session_id: str) -> dict[str, Any] | None:
        summary = self.fetch_summary(session_id)
        if not summary:
            return None
        return {
            "session_id": summary.session_id,
            "user_id": summary.user_id,
            "text_report": self.format_summary(summary),
            "details": summary.to_dict(),
        }
