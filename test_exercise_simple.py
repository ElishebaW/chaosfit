#!/usr/bin/env python3
"""
Simple test to verify exercise tracking logic without Firestore dependencies.
Tests the core exercise tracking functionality.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from live_agent.session_manager import SessionManager, SessionState


def test_exercise_tracking_simple():
    """Test exercise tracking without Firestore."""
    print("🧪 Testing Exercise Tracking Logic")
    print("=" * 50)
    
    # Create session manager (without Firestore)
    session_manager = SessionManager()
    session_id = "test-session-multi-exercise"
    
    # Create initial session state manually
    from backend.firestore.schema import utc_now_iso
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
    print(f"\n📊 Final Session State:")
    print(f"   🏃 Exercise History: {final_state.exercise_history}")
    print(f"   🎯 Current Exercise: {final_state.current_exercise}")
    print(f"   🔢 Total Reps: {final_state.cumulative_rep_count}")
    print(f"   ⚠️  Form Corrections: {final_state.form_corrections}")
    
    # Simulate session summary creation
    session_manager.complete_session(session_id)
    
    print(f"\n✅ Session summary would be created with:")
    print(f"   📝 Exercise Type: {final_state.current_exercise} (last exercise)")
    print(f"   🔢 Total Reps: {final_state.cumulative_rep_count} (cumulative from ALL exercises)")
    print(f"   ⚠️  Total Corrections: {len(final_state.form_corrections)} (ALL corrections)")
    print(f"   📝 Corrections List: {final_state.form_corrections}")
    
    print(f"\n🎯 Integration Test Complete!")
    print("=" * 50)
    
    # Verify expectations
    expected_exercises = ["jumping_jack", "air_squat", "push_up"]
    actual_exercises = final_state.exercise_history
    
    print(f"\n✅ Verification Results:")
    print(f"   🏃 Expected exercises: {expected_exercises}")
    print(f"   🏃 Actual exercises: {actual_exercises}")
    
    if set(expected_exercises) == set(actual_exercises):
        print("   ✅ All exercises properly tracked!")
    else:
        missing = set(expected_exercises) - set(actual_exercises)
        print(f"   ❌ Missing exercises: {missing}")
    
    if final_state.cumulative_rep_count == 33:  # 10 + 15 + 8
        print("   ✅ Rep counting correct!")
    else:
        print(f"   ❌ Rep counting error: expected 33, got {final_state.cumulative_rep_count}")
    
    if len(final_state.form_corrections) == 5:  # 2 + 2 + 1
        print("   ✅ Form corrections tracking correct!")
    else:
        print(f"   ❌ Form corrections error: expected 5, got {len(final_state.form_corrections)}")
    
    # Test summary display expectations
    print(f"\n📱 Expected Summary Page Display:")
    print(f"   🏃 Exercise: PUSH_UP (last exercise)")
    print(f"   🔢 Reps: 33 (cumulative total)")
    print(f"   ⚠️  Corrections: 5 (total from all exercises)")
    print(f"   📝 List: ['keep back straight', 'land softly', 'lower hips more', 'keep chest up', 'full extension', 'controlled descent']")
    
    return final_state


if __name__ == "__main__":
    test_exercise_tracking_simple()
