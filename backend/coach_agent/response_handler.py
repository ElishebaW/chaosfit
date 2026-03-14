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
        self._exercise_library = None
        self._load_exercise_library()
        self.correction_patterns = [
            r'CORRECTION:\s*(.+)',
            r'Safety correction:\s*(.+)',
            r'correction:\s*(.+)',
            r'Form correction:\s*(.+)',
            r'Your form:\s*(.+)',
            r'Try:\s*(.+)',
            r'Keep your:\s*(.+)',
            r'Make sure:\s*(.+)',
            r'Avoid:\s*(.+)',
            r'Adjust:\s*(.+)',
        ]
        self.rep_count_patterns = [
            r'(\d+)\s+more',
            r'do\s+(\d+)',
            r'(\d+)\s+reps?',
            r'let\'s\s+do\s+(\d+)',
        ]
        self.exercise_type_patterns = [
            # Essential exercise patterns only
            r'(air_squat|air\s+squat|squat|squatting|squats)',
            r'(push_up|push\s+up|pushup|push\s+ups|pushups)',
            r'(plank|planking|front\s+plank|plank\s+hold)',
            r'(reverse_lunge|lunge|lunging|lunges|reverse\s+lunge)',
            r'(mountain_climber|mountain\s+climber|mountain\s+climbers)',
            r'(jumping_jack|jumping\s+jack|jumping\s+jacks)',
        ]
    
    def _load_exercise_library(self):
        """Load exercise library for validation."""
        try:
            from backend.routines import load_exercise_library
            self._exercise_library = load_exercise_library()
        except Exception as e:
            logger.debug(f"Failed to load exercise library: {e}")
            self._exercise_library = None
    
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
        
        # Fallback: if no corrections found but text contains coaching cues, extract as correction
        if not extracted["form_corrections"] and self._contains_coaching_cues(text):
            # Extract the first sentence as a correction
            sentences = re.split(r'[.!?]', text)
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and len(sentence) > 5 and len(sentence) < 100:
                    extracted["form_corrections"].append(sentence)
                    extracted["is_interruption"] = True
                    break
        
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
                raw_exercise = match.group(1).lower()
                # Normalize to exercise library ID
                exercise_type = self._normalize_exercise_name(raw_exercise)
                # Validate against exercise library
                if self._validate_exercise(exercise_type):
                    extracted["exercise_type"] = exercise_type
                else:
                    logger.debug(f"Exercise not found in library: {exercise_type}")
                break
        
        return extracted
    
    def _normalize_exercise_name(self, raw_exercise: str) -> str:
        """Normalize exercise name to match exercise library ID."""
        # Essential exercise mapping only
        exercise_mapping = {
            'air squat': 'air_squat',
            'squat': 'air_squat',
            'squatting': 'air_squat',
            'squats': 'air_squat',
            'push up': 'push_up',
            'pushup': 'push_up',
            'push ups': 'push_up',
            'pushups': 'push_up',
            'plank': 'plank',
            'planking': 'plank',
            'front plank': 'plank',
            'plank hold': 'plank',
            'lunge': 'reverse_lunge',
            'lunging': 'reverse_lunge',
            'lunges': 'reverse_lunge',
            'reverse lunge': 'reverse_lunge',
            'mountain climber': 'mountain_climber',
            'mountain climbers': 'mountain_climber',
            'jumping jack': 'jumping_jack',
            'jumping jacks': 'jumping_jack',
        }
        
        # Return the normalized exercise ID or the original if not found
        return exercise_mapping.get(raw_exercise.replace(' ', '_'), raw_exercise.replace(' ', '_'))
    
    def _contains_coaching_cues(self, text: str) -> bool:
        """Check if text contains coaching cues that suggest form corrections."""
        coaching_cues = [
            'keep your', 'make sure', 'try to', 'avoid', 'adjust', 'position',
            'form', 'posture', 'alignment', 'chest', 'back', 'knees', 'hips',
            'shoulders', 'core', 'feet', 'hands', 'elbows', 'head', 'neck',
            'lower', 'higher', 'wider', 'narrower', 'straight', 'bent',
            'tighten', 'engage', 'relax', 'breathe', 'focus', 'concentrate'
        ]
        text_lower = text.lower()
        return any(cue in text_lower for cue in coaching_cues)
    
    def _validate_exercise(self, exercise_id: str) -> bool:
        """Validate exercise ID against the exercise library."""
        if not self._exercise_library:
            # If library not loaded, accept the exercise (fallback behavior)
            return True
        
        try:
            self._exercise_library.get(exercise_id)
            return True
        except KeyError:
            return False
    
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
            logger.debug(f"Created exercise event for {extracted.get('exercise_type', 'unknown')}")
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
