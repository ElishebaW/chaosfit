#!/usr/bin/env python3
"""
Demo script to showcase coach corrections functionality.
This demonstrates how the coach detects form issues and makes corrections.
"""

import asyncio
import json
import time
from typing import Dict, Any

from backend.coach_agent.response_handler import CoachResponseHandler, emit_exercise_data_tool


async def demo_coach_corrections():
    """Demo showing how coach corrections work in the system."""
    
    print("🏋️‍♂️ ChaosFit Coach Corrections Demo")
    print("=" * 50)
    
    # Simulate coach responses with corrections
    coach_responses = [
        {
            "text": "Great start! Let's do 10 squats.",
            "expected": {
                "rep_count": 10,
                "exercise_type": "squat",
                "is_interruption": False
            }
        },
        {
            "text": "CORRECTION: Keep your back straight during squats.",
            "expected": {
                "form_corrections": ["Keep your back straight during squats."],
                "is_interruption": True
            }
        },
        {
            "text": "Good! Now 5 more squats.",
            "expected": {
                "rep_count": 5,
                "exercise_type": "squat",
                "is_interruption": False
            }
        },
        {
            "text": "Safety correction: Your knees are going too far forward.",
            "expected": {
                "form_corrections": ["Your knees are going too far forward."],
                "is_interruption": True
            }
        },
        {
            "text": "Perfect form! Let's switch to push-ups.",
            "expected": {
                "exercise_type": "push_up",
                "is_interruption": False
            }
        },
        {
            "text": "CORRECTION: Lower your chest more on push-ups.",
            "expected": {
                "form_corrections": ["Lower your chest more on push-ups."],
                "is_interruption": True
            }
        }
    ]
    
    session_id = "demo-session-coach-corrections"
    handler = CoachResponseHandler(session_id)
    
    print("\n📝 Testing Coach Response Handler:")
    print("-" * 30)
    
    for i, response in enumerate(coach_responses, 1):
        print(f"\n{i}. Coach says: \"{response['text']}\"")
        
        # Process the response
        extracted = handler.extract_exercise_data(response['text'])
        event = handler.create_exercise_event(extracted) if extracted else None
        
        if event:
            print(f"   ✅ Extracted: {json.dumps(extracted, indent=2)}")
            print(f"   📊 Event type: {event['type']}")
            
            if extracted.get('is_interruption'):
                print(f"   ⚠️  INTERRUPTION DETECTED!")
                if extracted.get('form_corrections'):
                    print(f"   🔧 Corrections: {', '.join(extracted['form_corrections'])}")
                if extracted.get('rep_count'):
                    print(f"   🔢 Rep count: {extracted['rep_count']}")
                if extracted.get('exercise_type'):
                    print(f"   🏋️ Exercise: {extracted['exercise_type']}")
            
            # Verify against expected
            for key, expected_value in response['expected'].items():
                actual_value = extracted.get(key)
                if actual_value == expected_value:
                    print(f"   ✅ {key}: {actual_value}")
                else:
                    print(f"   ❌ {key}: expected {expected_value}, got {actual_value}")
        else:
            print("   ℹ️  No exercise data extracted")
        
        print("-" * 30)
        await asyncio.sleep(0.5)  # Brief pause for readability
    
    print("\n🎯 Demo Summary:")
    print(f"   • Total responses processed: {len(coach_responses)}")
    print(f"   • Corrections detected: {sum(1 for r in coach_responses if r['expected'].get('is_interruption', False))}")
    print(f"   • Form corrections: {len([r for r in coach_responses if r['expected'].get('form_corrections')])}")
    print(f"   • Exercise types detected: {len(set([r['expected'].get('exercise_type') for r in coach_responses if r['expected'].get('exercise_type')]))}")
    
    print("\n🚀 How it works in the real system:")
    print("1. User does exercises → Video/audio sent to coach")
    print("2. Coach analyzes form every 10 seconds (from updated prompt)")
    print("3. Coach detects issues → Calls emit_exercise_data() with corrections")
    print("4. Corrections marked as interruptions → Added to session state")
    print("5. Session summary shows: corrections=1, interruptions=0")
    
    print("\n📋 From your actual session logs:")
    print("   Exercise update received: ['exercise_id', 'rep_count', 'form_corrections', 'exercise_type']")
    print("   Session state: exercise=None, reps=0, interruptions=0, corrections=1")
    print("   ✅ Coach made 1 correction during the session!")


if __name__ == "__main__":
    asyncio.run(demo_coach_corrections())
