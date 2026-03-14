# ChaosFit: AI-Powered Fitness Coaching for Busy People

An intelligent fitness coaching assistant that adapts to real-life constraints, helping people stay fit without gyms, equipment, or dedicated workout time.

## Project Summary & Features

ChaosFit is a real-time AI fitness coach that meets people exactly where they are—whether they have 12 minutes during nap time or just a 6x6ft corner of their living room. Powered by Gemini Live API's multimodal capabilities, the system provides personalized coaching that adapts dynamically to available time, space, and energy levels.

### Key Features
- **Real-time form feedback** using video streaming and AI analysis
- **Adaptive workout generation** based on immediate constraints (time, space, equipment)
- **Voice-first interaction** for hands-free coaching during workouts
- **Session interruption handling** for real-life parenting scenarios (baby cries, calls)
- **Progress tracking** with automatic exercise detection and rep counting
- **Zero equipment required** - all workouts use bodyweight exercises

### Who It's For

ChaosFit is designed for anyone who needs to maintain fitness despite unpredictable schedules and limited resources:

#### **Parents with Young Children**
- Travel to gyms and scheduled appointments is impractical
- Need workouts that fit into 12-minute nap windows
- Limited space at home for dedicated workout areas
- Can't afford expensive equipment ($2,000+ home gyms)
- Need hands-free coaching while managing children

#### **Busy Professionals** 
- Demanding work schedules with unpredictable hours
- Remote workers needing quick exercise breaks between meetings
- Business travelers requiring hotel room-friendly workouts
- Anyone with limited time windows needing efficient, effective exercise

#### **Individuals in Recovery**
- Recovering from illness or injury needing gentle, adaptive exercise
- People with chronic conditions requiring modified workouts
- Those needing low-impact exercise options during recovery periods
- Anyone needing to gradually return to fitness with proper guidance

## Functionality

### How the AI Coach Works
ChaosFit uses Gemini Live API's multimodal capabilities to create an interactive coaching experience:

1. **Continuous audio streaming** enables natural conversation with the AI coach
2. **Periodic video frame streaming** (1 FPS) provides visual context for form analysis
3. **Real-time processing** allows the coach to interrupt and provide immediate corrections
4. **Adaptive routines engine** generates workouts based on available time and constraints

## Quick Start Guide

### Spin-Up Instructions

#### Prerequisites
- **Python 3.11+** (tested with Python 3.11)
- **uv package manager** (recommended) or pip/venv
- **Google Cloud Project** (for Vertex AI) or Google AI Studio API key
- **Modern browser** with camera/microphone support (Chrome/Edge recommended)
- **6GB+ RAM** and **2+ CPU cores** for optimal performance

#### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/chaosfit.git
   cd chaosfit
   ```

2. **Set up environment**
```bash
   cp .env.example .env
```

3. **Add your API key** — edit `.env`:
```env
   GOOGLE_GENAI_USE_VERTEXAI=FALSE
   GOOGLE_API_KEY=<your-gemini-api-key>
   DEMO_AGENT_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
   ENABLE_FIRESTORE=true
   GOOGLE_CLOUD_PROJECT=chaos-fit
```

4. **Install dependencies**
   
   Using uv (recommended):
   ```bash
   uv sync
   ```
   
   Using pip/venv:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r backend/requirements.txt
   ```

#### How to Run Locally

1. **Start the backend server**
   ```bash
   uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Open the application**
   - Navigate to: `http://localhost:8000`
   - Allow camera and microphone permissions when prompted

3. **Verify installation**
   - Health check: `http://localhost:8000/healthz`
   - Should return `{"status": "healthy"}`

#### Expected Output & Verification

1. **Successful startup** shows:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000
   INFO:     Started reloader process
   INFO:     Started server process
   ```

2. **Browser interface** displays:
   - ChaosFit logo and session controls
   - "Start Audio" and "Start Session" buttons
   - Webcam preview area and transcript console

3. **Test basic functionality**:
   - Click "Start Audio" - microphone should activate
   - Click "Start Session" - camera preview appears
   - Say "Show me a quick workout" - AI coach should respond
   - Check browser console for WebSocket connection logs

4. **Verify WebSocket connection**:
   - Open browser developer tools
   - Check Network tab for WebSocket connection to `/ws/{user_id}/{session_id}`
   - Should see "Connected" status and live message exchange

### User Flow: From Start to Summary

Here's exactly how to use ChaosFit from setup to results:

1. **Start the Application**
   ```bash
   uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```
   Open `http://localhost:8000` in your browser

2. **Begin Your Workout**
   - Click **Start Session** to begin camera and microphone streaming
   - Tell the coach what workout you want to do today, or wait — the coach will prompt you

3. **Follow AI Guidance**
   - Perform exercises as instructed by the coach
   - Receive real-time form corrections through voice feedback
   - System automatically tracks reps and exercise type
   - Coach adapts based on your form and energy levels

4. **Handle Interruptions**
   - Click "Pause Session" if baby cries or you need a break
   - Click "Resume Session" when ready to continue

### WebSocket Message Contract (UI Integration)

The frontend communicates with the backend over a WebSocket:

- **URL**: `/ws/{user_id}/{session_id}`
- **Direction**:
  - Client-to-server: JSON messages (and audio/video frames)
  - Server-to-client: streaming Gemini Live events + ChaosFit control messages

#### Client → Server: Optional `session_setup`

Send this once after connecting (optional). If not sent, the session still works, but the server will fall back to unknown-time adaptive blocks.

```json
{
  "type": "session_setup",
  "duration_minutes": 12,
  "equipment_available": [],
  "prefer_low_impact": true,
  "level": "beginner"
}
```

- **`duration_minutes`**
  - `5 | 12 | 20` generates a timeboxed plan.
  - Omit or set to an invalid value to use unknown-time mode.
- **`equipment_available`**
  - List of strings (e.g. `["mat", "dumbbells"]`).
- **`prefer_low_impact`**
  - Boolean; if true, routines avoid higher-impact cardio where possible.
- **`level`**
  - Optional string. Current scheduling uses this as a hint.

#### Server → Client: `session_setup_confirmed`

After `session_setup`, the server responds with the generated routine plan.

```json
{
  "type": "session_setup_confirmed",
  "routine_plan": {
    "mode": "timeboxed",
    "duration_minutes": 12,
    "total_duration_sec": 720,
    "library_version": "...",
    "blocks": [
      {
        "name": "Warmup",
        "mode": "warmup",
        "duration_sec": 120,
        "items": [{"exercise_id": "...", "prescription": {"type": "..."}}],
        "voice_script": "..."
      }
    ]
  }
}
```

The backend also injects the routine plan into the coach context so the coach can follow it.

5. **End Session & Get Summary**
   - Click "End Session" when workout is complete
   - System automatically generates detailed summary including:
     - Exercises performed and rep counts
     - Form corrections received
     - Total interruptions and recovery time
     - Performance insights and recommendations

**Example Session Summary Output:**
```json
{
  "session_id": "demo-session-abc123",
  "user_id": "demo-user",
  "exercise_type": "air_squat",
  "rep_count": 15,
  "interruption_count": 2,
  "form_corrections": [
    "Keep your chest up — you're rounding forward at the bottom.",
    "Drive your knees out, they're caving in on the way up."
  ],
  "session_duration_sec": 312,
  "started_at": "2026-03-14T11:22:56+00:00",
  "ended_at": "2026-03-14T11:28:08+00:00",
  "summary_text": "Strong effort on the air squats. Focus on chest position and knee tracking next session.",
  "motivational_closing_line": "Good work. Show up tomorrow."
}
```

## Technologies Used

### Backend Stack
- **FastAPI** - Python web framework for WebSocket connections
- **Google ADK** - Application Development Kit for Gemini Live API integration
- **Gemini Live API** - Multimodal AI model for real-time coaching
- **Google Cloud Firestore** - NoSQL database for session persistence
- **Python 3.11+** - Core backend language

### Frontend Stack
- **HTML5/CSS3/JavaScript** - Web-based user interface
- **WebSocket API** - Real-time communication with backend
- **WebRTC** - Camera and microphone access for streaming
- **Canvas API** - Visual overlay for motion tracking and form feedback

### Infrastructure & DevOps
- **uv** - Fast Python package manager
- **Uvicorn** - ASGI server for FastAPI deployment
- **Google Cloud Platform** - Hosting and database services
- **Docker-ready** - Containerized deployment support

### ML/AI Components
- **Gemini Live API (gemini-2.5-flash-native-audio-preview-12-2025)** - Real-time multimodal AI
- **Custom exercise detection** - Pattern matching for workout identification
- **Form analysis algorithms** - Computer vision for posture assessment
- **Adaptive scheduling engine** - Dynamic workout optimization

### Troubleshooting Common Issues

#### Import Errors
```bash
# Error: Could not import module "main"
# Solution: Use correct module path
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

#### Camera/Microphone Access
- Use `http://localhost:8000` (not `0.0.0.0`) in browser
- Check browser permissions for camera/microphone
- Try refreshing the page (`Cmd+Shift+R`)

#### API Connection Issues
- Verify `.env` file contains correct API keys
- Check Google Cloud project permissions
- Ensure model name matches available APIs

## Data Sources

### Exercise Library
- **Manually curated exercise database** with 20+ bodyweight movements
- **Professional coaching cues** adapted for AI delivery
- **Form correction patterns** based on certified trainer expertise
- **Progression scaling** for different fitness levels

### Training Data Sources
- **Public fitness databases** referenced for exercise form standards
- **Certified personal trainer knowledge** embedded in coaching prompts
- **Biomechanics principles** applied to movement analysis
- **User interaction patterns** from real-world testing sessions

### No External Video Databases
- **Privacy-first approach** - no user video data stored or used for training
- **Real-time processing only** - video frames analyzed immediately then discarded
- **Synthetic data generation** for form analysis algorithm development

## Findings & Learnings

### Key Insights from Building ChaosFit

#### What Worked Well
- **Gemini Live API's low-latency audio** created natural coaching conversations
- **1 FPS video streaming** provided sufficient visual context without bandwidth issues
- **Adaptive scheduling** successfully handled unpredictable scenarios
- **Voice-first interaction** proved essential for hands-free workout experience

#### Challenges Overcome
- **Session state management** - Solved race conditions in summary generation
- **Exercise detection accuracy** - Improved pattern matching for reliable rep counting
- **Real-time interruption handling** - Built robust pause/resume for baby care scenarios
- **Form feedback precision** - Balanced immediate corrections with encouraging coaching style

#### How Gemini Live API Enabled This Solution
- **Native audio streaming** allowed natural conversation without "press-to-talk" buttons
- **Multimodal processing** combined video context with voice coaching seamlessly
- **Real-time interruption capability** crucial for dynamic parenting environments
- **Low-latency responses** made coaching feel responsive and engaging

#### Surprising Discoveries
- **Parents prefer shorter, more frequent workouts** over longer sessions
- **Form corrections work best when concise and immediate** rather than detailed explanations
- **Session interruption recovery** is as important as the workout itself
- **Visual feedback overlays** significantly improve user engagement and form awareness

### Technical Trade-offs
- **Chose 1 FPS over high-frequency pose tracking** for better real-time performance
- **Prioritized voice interaction over complex UI** for hands-free parenting scenarios
- **Used manual exercise curation** over automated generation for safety and reliability
- **Implemented client-side processing** for visual feedback to reduce server load

### What We'd Build With More Time
- **Improved Pause/Resume Workflow** — Smoother UX for pausing and resuming, including better state recovery and clearer user feedback during paused state.
- **Better Session Setup Experience** — A guided pre-session flow where the user sets their goal, exercise type, and duration before streaming begins.
- **Adaptive Scheduling Engine** — Dynamically restructure workout blocks mid-session based on remaining time, fatigue signals, and interruptions.
- **Advanced pose estimation** for more precise form analysis
- **Progressive workout programs** spanning multiple sessions
- **Social features** for parent community support
- **Integration with wearables** for heart rate and intensity tracking
- **Mobile app** for better camera positioning and user experience

## License

Apache License 2.0 - see LICENSE file for details.

## Contributing

We welcome contributions! Please see CONTRIBUTING.md for guidelines on submitting pull requests and issue reports.

## Support

For questions or support during hackathon judging, please contact the development team through the repository issues or hackathon communication channels.
