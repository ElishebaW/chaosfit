#!/usr/bin/env python3
"""
Simple test to verify exercise tracking logic without Firestore dependencies.
Tests the core exercise tracking functionality.
"""

from backend.live_agent.session_manager import SessionManager, SessionState
from backend.firestore.schema import utc_now_iso


def test_exercise_tracking_simple():
    """Test exercise tracking without Firestore."""
    session_manager = SessionManager()
    session_id = "test-session-multi-exercise"

    # Create initial session state manually
    state = SessionState(
        session_id=session_id,
        parent_id="test-user",
        started_at=utc_now_iso(),
        status="active"
    )
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
    print("\n📊 Final Session State:")
    print(f"   🏃 Exercise History: {final_state.exercise_history}")
    print(f"   🎯 Current Exercise: {final_state.current_exercise}")
    print(f"   🔢 Total Reps: {final_state.cumulative_rep_count}")
    print(f"   ⚠️  Form Corrections: {final_state.form_corrections}")
    
    # Simulate session summary creation
    session_manager.complete_session(session_id)
    
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
    test_exercise_tracking_simple()
