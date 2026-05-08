# ChaosFit: Audio/Video Sync & Latency Tracking

> **Note:** Judges are reviewing the repo — file this as a GitHub issue in `ElishebaW/chaosfit` after judging is complete.

## Problem

The coaching agent's audio feedback is not synchronized with video frames. A correction like "keep your chest up" may be responding to a frame that is 1–2+ seconds stale by the time the audio plays. Under poor network conditions this gap widens silently — the user gets no indication of degradation.

**Current behavior:**
- Video frames sent at 1 FPS with no timestamp metadata
- Audio plays independently of video; no mechanism ties a coaching response to the frame that triggered it
- Round-trip latency (frame capture → WebSocket → Gemini → audio playback) is unmeasured and unmonitored

## Root Cause

Three compounding gaps:

1. **No frame timestamps** — `app.js` sends frames as base64 JSON with no capture time, so the server cannot determine frame age when a response arrives
2. **No latency measurement** — no instrumentation for WebSocket RTT, Gemini processing time, or audio buffer level
3. **No playback alignment** — `pcm-player-processor.js` plays audio immediately on receipt with no delay to compensate for the feedback loop lag

## Proposed Fixes

### 1. Stamp video frames with client capture timestamp
```js
// app.js — video send block
const payload = {
  image: base64data,
  capturedAt: Date.now(),   // add this
};
```

### 2. Track frame age on the server
```python
# main.py — upstream handler
frame_age_ms = (time.time() * 1000) - msg.get("capturedAt", 0)
if frame_age_ms > 3000:
    logger.warning(f"Stale frame ({frame_age_ms:.0f}ms), skipping")
    continue
```

### 3. Add latency telemetry
- Client records `sentAt` timestamp on each WebSocket message
- Server echoes it back in the response envelope
- Client computes RTT and logs to console / exposes as metric
- Surface degradation to user if RTT exceeds threshold (e.g. >3s)

### 4. Adaptive frame rate
- Reduce from fixed 1 FPS to 0.5 FPS if measured RTT > 2s
- Resume 1 FPS when RTT recovers
- Prevents backlog buildup under slow networks

### 5. Buffer audio by average RTT
- Delay audio playback by the rolling average round-trip time
- Keeps coaching corrections temporally aligned with the movement that prompted them

## Acceptance Criteria

- [ ] Video frames include `capturedAt` timestamp (client-side ms epoch)
- [ ] Server logs a warning and skips frames older than a configurable threshold (default 3s)
- [ ] Client measures and logs WebSocket round-trip time per message
- [ ] Frame rate adapts down when RTT exceeds 2s
- [ ] Audio playback buffered by average RTT so corrections align with current movement
- [ ] User receives a visible indicator if coaching latency exceeds acceptable threshold

## Key File Locations

| Component | File | Lines | Notes |
|-----------|------|-------|-------|
| Video frame interval | `app.js` | 1394 | Fixed 1000ms |
| Frame encode skip | `app.js` | 1539 | `isFrameEncodeInFlight` guard |
| Video send | `app.js` | 1562 | Add `capturedAt` here |
| Audio output buffer | `pcm-player-processor.js` | 10 | 24kHz × 180 sec ring buffer |
| Buffer overflow | `pcm-player-processor.js` | 43–45 | Silently overwrites oldest data |
| Upstream handler | `main.py` | 273–415 | Add frame age check here |
