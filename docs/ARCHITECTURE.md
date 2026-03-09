# Architecture (ChaosFit)

ChaosFit is a real-time coaching loop built around bidirectional audio + periodic video frame streaming.

## High-level flow
- Browser UI streams mic audio and periodic video frames to FastAPI over WebSocket.
- Backend forwards stream context to Gemini Live via ADK.
- Live agent produces short, interruptible coaching guidance.
- Routines engine (Person 4) generates either:
  - a fixed 5/12/20-minute plan, or
  - block-by-block “unknown time” recommendations driven by live context.

## Where routines fit
The routines module (`backend/routines/*`) provides exercise metadata (IDs, cues, corrections) and returns a `voice_script` per block that the live agent can speak. Backend endpoints (Person 3) should call the routines engine and pass the resulting block/plan into the session lifecycle; the frontend (Person 2) renders the plan or current block and sends back history + live signals as the session progresses.

