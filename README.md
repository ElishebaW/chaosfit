# ChaosFit Live Coach (ADK Bidi)

ChaosFit is a real-time workout coaching app built on Google ADK bidirectional streaming.
It supports:
- live text chat
- live microphone input/output
- camera photo capture + form feedback

## Tech stack
- FastAPI + WebSocket
- Google ADK (`Runner.run_live` + `LiveRequestQueue`)
- Gemini Live model (native audio)
- Static frontend (copied/adapted from `bidi-demo`)

## Prerequisites
- Python `>=3.10` (tested with Python 3.11)
- `uv` installed (recommended)
- Browser with mic/camera support (latest Chrome/Edge recommended)

## 1) Configure environment
Create/update `.env` in repo root.

### Option A: Gemini Live API (AI Studio key)
```env
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=<YOUR_GOOGLE_API_KEY>
DEMO_AGENT_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
```

### Option B: Vertex AI Live API
```env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=<YOUR_PROJECT_ID>
GOOGLE_CLOUD_LOCATION=us-central1
DEMO_AGENT_MODEL=gemini-live-2.5-flash-native-audio
```

## 2) Install dependencies
Using `uv`:
```bash
cd /Users/elishebawiggins/projects/chaosfit
uv sync
```

Or using pip/venv:
```bash
cd /Users/elishebawiggins/projects/chaosfit
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## 3) Run the app
```bash
cd /Users/elishebawiggins/projects/chaosfit
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open:
- `http://localhost:8000`

Health check:
- `http://localhost:8000/healthz`

## 4) Use audio + camera
1. Click `Start Audio` to enable microphone streaming.
2. Speak naturally; model can respond in audio/text depending on model config.
3. Click `Camera` to open preview and send an image.
4. App sends image + follow-up prompt for immediate form feedback.
5. Click `Stop Audio` to stop mic, then `Start Audio` to restart.

## 5) WebSocket endpoint
Frontend connects to:
- `/ws/{user_id}/{session_id}`

Example:
- `ws://localhost:8000/ws/demo-user/demo-session-123`

## Troubleshooting

### `Error loading ASGI app. Could not import module "main"`
Use:
```bash
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
Do not use `main:app` from repo root.

### Camera/mic permission errors
- Use `http://localhost:8000` (not `0.0.0.0` in browser URL).
- Allow browser camera/mic permissions.
- Prefer latest Chrome/Edge.

### Connected but no model response after image
The app now auto-sends a follow-up text turn after image upload. If still silent, verify API key/project/model in `.env`.

### Audio events visible in console even with `Show audio` unchecked
Already fixed in current `app.js`; hard refresh browser (`Cmd+Shift+R`) to load latest JS.

## Repo layout
- `backend/main.py`: FastAPI app + ADK websocket flow
- `backend/coach_agent/agent.py`: model/instruction config
- `backend/static/`: frontend UI (index/css/js)
- `backend/requirements.txt`: pip dependency fallback
- `pyproject.toml`: uv project config
