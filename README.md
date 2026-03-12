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

### User Interaction Flow
1. **Session Setup**: User specifies available time (5/12/20 minutes or "unknown") and constraints
2. **Live Coaching**: User starts audio/video streaming and begins following AI guidance
3. **Dynamic Adaptation**: Coach modifies exercises based on form, fatigue, and interruptions
4. **Progress Tracking**: System automatically detects exercises, counts reps, and records corrections
5. **Session Summary**: Detailed report saved with performance metrics and coaching insights

### Core Capabilities in Action
- **"I have 12 minutes during nap time"** → Generates optimized 12-minute routine
- **"My baby is crying"** → Automatically pauses and resumes when ready
- **"Only have a 6x6ft space"** → Selects space-appropriate exercises
- **Real-time form correction** → "Lower your hips more" when squat form needs improvement
- **Fatigue adaptation** → Switches to lower-impact exercises when user shows signs of fatigue

### User Flow: From Start to Summary

Here's exactly how to use ChaosFit from setup to results:

1. **Start the Application**
   ```bash
   uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```
   Open `http://localhost:8000` in your browser

2. **Begin Your Workout**
   - Click "Start Audio" to enable microphone
   - Click "Start Session" to begin camera streaming
   - Say: *"What's a good workout for today?"*
   - AI coach will respond with personalized exercise suggestions

3. **Follow AI Guidance**
   - Perform exercises as instructed by the coach
   - Receive real-time form corrections through voice feedback
   - System automatically tracks reps and exercise type
   - Coach adapts based on your form and energy levels

4. **Handle Interruptions**
   - Click "Pause Session" if baby cries or you need a break
   - Click "Resume Session" when ready to continue
   - Coach automatically adjusts workout based on remaining time

5. **End Session & Get Summary**
   - Click "End Session" when workout is complete
   - System automatically generates detailed summary including:
     - Exercises performed and rep counts
     - Form corrections received
     - Total interruptions and recovery time
     - Performance insights and recommendations

**Example Session Summary Output:**
```
Workout Complete! 
- 12 minutes of bodyweight exercises
- 45 total reps across 4 exercises
- 3 form corrections (squat depth, push-up form)
- 2 interruptions (baby cry, water break)
- Great consistency! Try adding 5 more reps next time.
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
   # Copy environment template
   cp .env.example .env
   
   # Edit .env with your API credentials
   # Choose Option A or B below:
   ```

3. **Configure API Access**

   **Option A: Gemini Live API (AI Studio)**
   ```env
   GOOGLE_GENAI_USE_VERTEXAI=FALSE
   GOOGLE_API_KEY=<your-gemini-api-key>
   DEMO_AGENT_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
   ENABLE_FIRESTORE=true
   GOOGLE_CLOUD_PROJECT=chaos-fit
   ```

   **Option B: Vertex AI Live API**
   ```env
   GOOGLE_GENAI_USE_VERTEXAI=TRUE
   GOOGLE_CLOUD_PROJECT=your_project_id
   GOOGLE_CLOUD_LOCATION=us-central1
   DEMO_AGENT_MODEL=gemini-live-2.5-flash-native-audio
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
