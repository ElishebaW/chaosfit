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

## Person 2 — session UI + sketch overlay
`SessionPage` glues `useLiveSession`, `WebcamFeed`, `TimerWidget`, and the sketch canvas together so the browser can:
- stream audio/video to the FastAPI `/ws/{user_id}/{session_id}` channel,
- surface live transcripts/errors, and
- emit exercise history alongside any `showSketch` toggles or overlay highlights.

The canvas runs synced `requestAnimationFrame` draws that follow pointer movement and pulse when Gemini transcripts mention keywords like “knee,” “form,” or “hip.” This overlay is a live visual signal that complements the green/amber/red status bubbles in the UI and gives judges a feel for how Person 2 captures real-time motion without a dedicated pose model.

