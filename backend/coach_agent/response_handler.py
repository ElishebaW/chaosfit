"""Response handler for ChaosFit coach to emit structured exercise events."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)


def generate_session_id() -> str:
    """Generate a unique session ID using timestamp and UUID."""
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8]
    return f"session-{timestamp}-{unique_id}"


class CoachResponseHandler:
    """Handles coach responses and emits structured exercise data events."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.correction_patterns = [
            r'CORRECTION:\s*(.+)',
            r'Safety correction:\s*(.+)',
            r'correction:\s*(.+)',
        ]
        self.rep_count_patterns = [
            r'(\d+)\s+more',
            r'do\s+(\d+)',
            r'(\d+)\s+reps?',
            r'let\'s\s+do\s+(\d+)',
        ]
        self.exercise_type_patterns = [
            r'(air\s+squat|squat|push\s+up|pull\s+up|plank|lunge|deadlift|bench\s+press)',
            r'(neck\s+stretch|shoulder\s+roll|arm\s+circle)',
        ]
    
    def extract_exercise_data(self, text: str) -> dict[str, Any]:
        """Extract structured exercise data from coach text response."""
        extracted = {
            "form_corrections": [],
            "rep_count": None,
            "exercise_type": None,
            "is_interruption": False,
        }
        
        # Extract form corrections
        for pattern in self.correction_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                correction = match.strip()
                if correction and correction not in extracted["form_corrections"]:
                    extracted["form_corrections"].append(correction)
                    extracted["is_interruption"] = True
        
        # Extract rep counts
        for pattern in self.rep_count_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    count = int(match.group(1))
                    if count > 0:
                        extracted["rep_count"] = count
                        break
                except (ValueError, IndexError):
                    continue
        
        # Extract exercise types
        for pattern in self.exercise_type_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                exercise_type = match.group(1).lower().replace(' ', '_')
                extracted["exercise_type"] = exercise_type
                break
        
        return extracted
    
    def create_exercise_event(self, extracted_data: dict[str, Any]) -> dict[str, Any]:
        """Create a structured exercise event from extracted data."""
        from backend.firestore.schema import utc_now_iso
        
        event = {
            "type": "exercise_update",
            "session_id": self.session_id,
            "timestamp": utc_now_iso(),
        }
        
        if extracted_data["form_corrections"]:
            event["form_corrections"] = extracted_data["form_corrections"]
        
        if extracted_data["rep_count"] is not None:
            event["rep_count"] = extracted_data["rep_count"]
        
        if extracted_data["exercise_type"]:
            event["exercise_type"] = extracted_data["exercise_type"]
            event["exercise_id"] = extracted_data["exercise_type"]  # Add exercise_id for session manager
        
        if extracted_data["is_interruption"]:
            event["interruption"] = True
        
        return event
    
    def process_response(self, response_text: str) -> dict[str, Any] | None:
        """Process coach response and return structured event if exercise data found."""
        if not response_text or not response_text.strip():
            return None
        
        extracted = self.extract_exercise_data(response_text)
        
        # Only create event if we found meaningful exercise data
        if (extracted["form_corrections"] or 
            extracted["rep_count"] is not None or 
            extracted["exercise_type"] is not None):
            
            event = self.create_exercise_event(extracted)
            logger.info(f"Created exercise event: {event}")
            return event
        
        return None


def emit_exercise_data(text: str, session_id: str = "") -> dict[str, Any]:
    """Tool for the coach to emit structured exercise data along with text responses.
    
    This tool should be called when the coach provides exercise instructions,
    corrections, or rep counts to ensure proper tracking in session summaries.
    
    Args:
        text: The coach's response text
        session_id: Current session ID (optional, will generate unique ID if not provided)
        
    Returns:
        Structured exercise data event
    """
    # Generate a unique session ID if not provided
    effective_session_id = session_id if session_id else generate_session_id()
    
    # Log the session ID being used
    if not session_id:
        logger.warning(f"No session_id provided to emit_exercise_data, generated: {effective_session_id}")
    else:
        logger.info(f"Using provided session_id: {effective_session_id}")
    
    handler = CoachResponseHandler(effective_session_id)
    event = handler.process_response(text)
    
    if event:
        return {
            "status": "success",
            "event": event,
            "message": "Exercise data extracted and structured",
            "session_id": effective_session_id  # Include for debugging
        }
    
    return {
        "status": "no_data",
        "message": "No exercise data found in response",
        "session_id": effective_session_id  # Include for debugging
    }


# Create the FunctionTool instance
emit_exercise_data_tool = FunctionTool(emit_exercise_data)
