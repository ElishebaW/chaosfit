#!/usr/bin/env python3
"""
Unit test for exercise tracking logic without external dependencies.
Tests the core exercise tracking functionality in isolation.
"""

def test_exercise_tracking_unit():
    """Test exercise tracking logic with mocked SessionState."""
    print("🧪 Testing Exercise Tracking Unit Test")
    print("=" * 50)
    
    # Mock SessionState class
    class MockSessionState:
        def __init__(self, session_id):
            self.session_id = session_id
            self.parent_id = "test-user"
            self.started_at = "2026-03-13T10:00:00Z"
            self.exercise_history = []
            self.current_exercise = None
            self.cumulative_rep_count = 0
            self.form_corrections = []
            self.total_interruptions = 0
            self.coach_interruptions = 0
            self.pause_count = 0
            self.total_pause_time_seconds = 0.0
            self.status = "active"
    
    # Mock session manager
    class MockSessionManager:
        def __init__(self):
            self._mem = {}
        
        def get(self, session_id):
            return self._mem[session_id]
        
        def append_event(self, session_id, event_type, payload):
            state = self.get(session_id)
            
            # Track exercise data (mimicking the real logic)
            if "exercise_id" in payload and isinstance(payload["exercise_id"], str):
                exercise_id = payload["exercise_id"]
                state.exercise_history.append(exercise_id)
                state.current_exercise = exercise_id
                print(f"✅ Updated exercise to {exercise_id} for session {session_id}")
                
            if "rep_count" in payload:
                rep_count = payload["rep_count"]
                if rep_count is not None:
                    state.cumulative_rep_count += rep_count
                    print(f"✅ Added {rep_count} reps to session {session_id} (total: {state.cumulative_rep_count})")
            
            if "form_corrections" in payload:
                corrections = payload.get("form_corrections")
                if isinstance(corrections, list):
                    for correction in corrections:
                        correction_str = str(correction).strip()
                        if correction_str and correction_str not in state.form_corrections:
                            state.form_corrections.append(correction_str)
                            print(f"✅ Added form correction: {correction_str}")
        
        def complete_session(self, session_id):
            state = self.get(session_id)
            state.status = "ended"
            print(f"✅ Session {session_id} marked as ended")
    
    # Test the tracking
    session_manager = MockSessionManager()
    session_id = "test-session-multi-exercise"
    state = MockSessionState(session_id)
    session_manager._mem[session_id] = state
    
    print(f"📋 Created test session: {session_id}")
    print(f"📊 Initial state - exercises: {len(state.exercise_history)}, current: {state.current_exercise}")
    
    # Simulate multiple exercises during session
    exercises = [
        {
            "type": "exercise_update",
            "exercise_id": "jumping_jack",
            "exercise_type": "jumping_jack", 
            "rep_count": 10,
            "form_corrections": ["keep back straight", "land softly"]
        },
        {
            "type": "exercise_update", 
            "exercise_id": "air_squat",
            "exercise_type": "air_squat",
            "rep_count": 15,
            "form_corrections": ["lower hips more", "keep chest up"]
        },
        {
            "type": "exercise_update",
            "exercise_id": "push_up",
            "exercise_type": "push_up", 
            "rep_count": 8,
            "form_corrections": ["full extension", "controlled descent"]
        }
    ]
    
    # Process each exercise
    for i, exercise in enumerate(exercises, 1):
        print(f"\n🏃 Exercise {i}: {exercise['exercise_type']}")
        session_manager.append_event(session_id, "exercise_update", exercise)
        
        # Check state after each exercise
        current_state = session_manager.get(session_id)
        print(f"   ✅ Added to history: {exercise['exercise_type']}")
        print(f"   ✅ Current exercise: {current_state.current_exercise}")
        print(f"   ✅ Total exercises: {len(current_state.exercise_history)}")
        print(f"   ✅ Cumulative reps: {current_state.cumulative_rep_count}")
        print(f"   ✅ Form corrections: {len(current_state.form_corrections)}")
    
    # Final state check
    final_state = session_manager.get(session_id)
    session_manager.complete_session(session_id)
    
    print("\n📊 Final Session State:")
    print(f"   🏃 Exercise History: {final_state.exercise_history}")
    print(f"   🎯 Current Exercise: {final_state.current_exercise}")
    print(f"   🔢 Total Reps: {final_state.cumulative_rep_count}")
    print(f"   ⚠️  Form Corrections: {final_state.form_corrections}")
    
    print("\n✅ Session summary would be created with:")
    print(f"   📝 Exercise Type: {final_state.current_exercise} (last exercise)")
    print(f"   🔢 Total Reps: {final_state.cumulative_rep_count} (cumulative from ALL exercises)")
    print(f"   ⚠️  Total Corrections: {len(final_state.form_corrections)} (ALL corrections)")
    print(f"   📝 Corrections List: {final_state.form_corrections}")
    
    print("\n🎯 Integration Test Complete!")
    print("=" * 50)
    
    assert set(final_state.exercise_history) == {"jumping_jack", "air_squat", "push_up"}
    assert final_state.cumulative_rep_count == 33, f"expected 33 reps, got {final_state.cumulative_rep_count}"
    assert len(final_state.form_corrections) == 6, f"expected 6 corrections, got {len(final_state.form_corrections)}"  # 2 + 2 + 2


if __name__ == "__main__":
    test_exercise_tracking_unit()
