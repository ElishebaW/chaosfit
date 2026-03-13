/**
 * app.js: JS code for the ChaosFit app.
 */

/**
 * WebSocket handling
 */

// Connect to server with a WebSocket connection
const userId = "demo-user";
const sessionId = "demo-session-" + Math.random().toString(36).substring(7);
let websocket = null;
let is_audio = false;

// Initialize event listeners when DOM is ready
function initializeApp() {
  setupEventListeners();
  connectWebsocket();
}

// Get checkbox elements for RunConfig options
const enableProactivityCheckbox = document.getElementById("enableProactivity");
const enableAffectiveDialogCheckbox = document.getElementById("enableAffectiveDialog");

// Reconnect WebSocket when RunConfig options change
function handleRunConfigChange() {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    addSystemMessage("Reconnecting with updated settings...");
    addConsoleEntry('outgoing', 'Reconnecting due to settings change', {
      proactivity: enableProactivityCheckbox.checked,
      affective_dialog: enableAffectiveDialogCheckbox.checked
    }, '🔄', 'system');
    websocket.close();
    // connectWebsocket() will be called by onclose handler after delay
  }
}

// Add change listeners to RunConfig checkboxes (only if elements exist)
function setupEventListeners() {
  if (enableProactivityCheckbox) {
    enableProactivityCheckbox.addEventListener("change", handleRunConfigChange);
  }
  if (enableAffectiveDialogCheckbox) {
    enableAffectiveDialogCheckbox.addEventListener("change", handleRunConfigChange);
  }
}

// Build WebSocket URL with RunConfig options as query parameters
function getWebSocketUrl() {
  // Use wss:// for HTTPS pages, ws:// for HTTP (localhost development)
  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const baseUrl = wsProtocol + "//" + window.location.host + "/ws/" + userId + "/" + sessionId;
  const params = new URLSearchParams();

  // Add proactivity option if checked
  if (enableProactivityCheckbox && enableProactivityCheckbox.checked) {
    params.append("proactivity", "true");
  }

  // Add affective dialog option if checked
  if (enableAffectiveDialogCheckbox && enableAffectiveDialogCheckbox.checked) {
    params.append("affective_dialog", "true");
  }

  const queryString = params.toString();
  return queryString ? baseUrl + "?" + queryString : baseUrl;
}

// Get DOM elements
const messageForm = document.getElementById("messageForm");
const messageInput = document.getElementById("message");
const messagesDiv = document.getElementById("messages");
const statusIndicator = document.getElementById("statusIndicator");
const statusText = document.getElementById("statusText");
const startSessionButton = document.getElementById("startSession");
const stopSessionButton = document.getElementById("stopSession");
const startSessionBtn = document.getElementById("startSessionBtn");
const stopSessionBtn = document.getElementById("stopSessionBtn");
const sessionStatusText = document.getElementById("sessionStatus");
const repCountEl = document.getElementById("repCount");
const incrementRepButton = document.getElementById("incrementRep");
const resetRepButton = document.getElementById("resetRep");
const timerDisplay = document.getElementById("timerDisplay");
const pauseTimerButton = document.getElementById("pauseTimer");
const resetTimerButton = document.getElementById("resetTimer");
const consoleContent = document.getElementById("consoleContent");
const clearConsoleBtn = document.getElementById("clearConsole");
const showAudioEventsCheckbox = document.getElementById("showAudioEvents");
const interruptionBanner = document.getElementById("interruptionBanner");
const sessionPauseBanner = document.getElementById("sessionPauseBanner");
const pauseSessionButton = document.getElementById("pauseSessionButton");
const resumeSessionButton = document.getElementById("resumeSessionButton");
const pauseBtn = document.getElementById("pauseBtn");
const resumeBtn = document.getElementById("resumeBtn");
let currentMessageId = null;
let currentBubbleElement = null;
let currentInputTranscriptionId = null;
let currentInputTranscriptionElement = null;
let currentOutputTranscriptionId = null;
let currentOutputTranscriptionElement = null;
let inputTranscriptionFinished = false; // Track if input transcription is complete for this turn
let hasOutputTranscriptionInTurn = false; // Track if output transcription delivered the response
let interruptionCount = 0;

// Exercise tracking variables
let currentExercise = null;
let exerciseRepCount = 0;
let formCorrections = [];
let sessionGoal = null;
let interruptionBannerTimer = null;
let isSessionPaused = false;
let currentPauseReason = null;

// Pause/Resume tracking variables
let sessionPaused = false;
let pauseStartTime = null;
let totalPauseTime = 0;

let hudRepCount = 0;
let hudTimerSeconds = 0;
let hudTimerInterval = null;
let hudTimerRunning = false;

function setHudSessionStatus(isLive) {
  if (!sessionStatusText) return;
  sessionStatusText.textContent = isLive ? "● LIVE" : "● OFFLINE";
}

function setHudRepCount(nextCount) {
  hudRepCount = nextCount;
  if (repCountEl) repCountEl.textContent = String(hudRepCount);
}

function formatHudTime(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}

function setHudTimerSeconds(nextSeconds) {
  hudTimerSeconds = nextSeconds;
  if (timerDisplay) timerDisplay.textContent = formatHudTime(hudTimerSeconds);
}

function startHudTimer() {
  if (hudTimerInterval) return;
  hudTimerRunning = true;
  hudTimerInterval = window.setInterval(() => {
    if (!hudTimerRunning) return;
    setHudTimerSeconds(hudTimerSeconds + 1);
  }, 1000);
}

function stopHudTimer() {
  hudTimerRunning = false;
  if (hudTimerInterval) {
    window.clearInterval(hudTimerInterval);
    hudTimerInterval = null;
  }
}

async function startSession() {
  try {
    // Step 1: Request camera access
    const videoStream = await navigator.mediaDevices.getUserMedia({ 
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: "user"
      }
    });
    
    // Step 2: Initialize audio (this will handle microphone access)
    try {
      await startAudio();
      
      // Set audio flag to true
      is_audio = true;
      console.log("Audio started, is_audio set to true");
    } catch (audioError) {
      console.warn("Audio failed to start, but continuing with session:", audioError);
      addSystemMessage("⚠️ Audio unavailable - video only session");
      // Don't throw error, allow session to continue without audio
    }
    
    // Verify microphone is working (only if audio started successfully)
    if (is_audio) {
      console.log("MicStream check:", micStream);
      console.log("MicStream tracks:", micStream?.getTracks());
      console.log("MicStream active:", micStream?.getTracks()?.[0]?.enabled);
      
      if (!micStream) {
        console.warn("Microphone stream is null, but continuing with video-only session");
        addSystemMessage("⚠️ Microphone not available - video only session");
      } else {
        // Check if microphone tracks are enabled
        const audioTracks = micStream.getAudioTracks();
        if (audioTracks.length === 0) {
          console.warn("No audio tracks found in microphone stream");
        }
        
        if (!audioTracks[0].enabled) {
          console.warn("Microphone track is disabled, enabling it...");
          audioTracks[0].enabled = true;
        }
      }
    }
    
    // Step 3: Combine streams
    const combinedStream = new MediaStream();
    if (micStream) {
      micStream.getTracks().forEach(track => combinedStream.addTrack(track));
    }
    videoStream.getTracks().forEach(track => combinedStream.addTrack(track));
    
    mediaStream = combinedStream;
    
    // Step 4: Display video preview
    const videoElement = document.getElementById("cameraPreview");
    const videoBgElement = document.getElementById("cameraPreviewBg");
    
    // Set both video elements to use the same stream
    videoElement.srcObject = videoStream;
    videoBgElement.srcObject = videoStream;
    
    videoElement.play();
    videoBgElement.play();
    
    // Step 5: Send session setup to backend
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      // Get user preferences from setup form
      const duration = document.getElementById("durationSelect").value;
      const level = document.getElementById("levelSelect").value;
      const preferLowImpact = document.getElementById("impactSelect").value === "true";
      
      // Get selected equipment
      const equipmentAvailable = [];
      const equipmentCheckboxes = document.querySelectorAll('.equipment-label input[type="checkbox"]:checked');
      equipmentCheckboxes.forEach(checkbox => {
        equipmentAvailable.push(checkbox.value);
      });
      
      const setupData = {
        type: "session_setup",
        duration_minutes: parseInt(duration),
        equipment_available: equipmentAvailable,
        prefer_low_impact: preferLowImpact,
        level: level
      };
      
      websocket.send(JSON.stringify(setupData));
      
      // Format user-friendly message
      const equipmentText = equipmentAvailable.length > 0 ? equipmentAvailable.join(", ") : "no equipment";
      const impactText = preferLowImpact ? "low impact" : "high impact";
      addSystemMessage(`📋 Session setup sent: ${duration}min ${level} workout, ${impactText}, ${equipmentText}`);
    }
    
    // Step 6: Set session status
    setHudSessionStatus(true);
    startHudTimer();
    
    // Step 7: Update UI
    if (startSessionBtn) startSessionBtn.style.display = "none";
    if (stopSessionBtn) stopSessionBtn.style.display = "inline-block";
    if (pauseBtn) pauseBtn.style.display = "inline-block";
    
    // Hide session setup panel
    const setupPanel = document.getElementById("sessionSetupPanel");
    if (setupPanel) {
      setupPanel.style.display = "none";
    }
    
    addSystemMessage("✅ Session started. Audio and video are active.");
    
  } catch (error) {
    console.error("Failed to start session:", error);
    addSystemMessage(`❌ Error: ${error.message}`);
  }
}

async function stopHudSession() {
  try {
    // Always send session end event with current exercise data (even if none)
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      sendSessionEnd();
    }
    
    await stopVideoStream();
    
    // Stop combined media stream
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }
    
    // Clear video elements
    const videoElement = document.getElementById("cameraPreview");
    const videoBgElement = document.getElementById("cameraPreviewBg");
    
    if (videoElement) {
      videoElement.srcObject = null;
    }
    
    if (videoBgElement) {
      videoBgElement.srcObject = null;
    }
  } catch (e) {
    console.warn("Failed to stop video stream:", e);
  }

  // Redirect to post-session summary screen.
  // Session ID is part of the WebSocket URL (/ws/{user_id}/{session_id}) and is available in this module.
  try {
    window.location.href = `/summary?session_id=${encodeURIComponent(sessionId)}`;
  } catch (e) {
    // Fall through to local UI reset if navigation fails.
  }

  // Reset HUD
  hudRepCount = 0;
  hudTimerSeconds = 0;
  setHudRepCount(0);
  setHudTimerSeconds(0);
  setHudSessionStatus(false);

  if (startSessionBtn) {
    startSessionBtn.style.display = "inline-block";
  }
  if (stopSessionBtn) stopSessionBtn.style.display = "none";
  if (pauseBtn) pauseBtn.style.display = "none";
  if (resumeBtn) resumeBtn.style.display = "none";
  
  // Show session setup panel again
  const setupPanel = document.getElementById("sessionSetupPanel");
  if (setupPanel) {
    setupPanel.style.display = "block";
  }
  
  // Reset pause tracking variables
  sessionPaused = false;
  pauseStartTime = null;
  totalPauseTime = 0;
}

async function stopSession() {
  try {
    // Stop audio if it's running
    if (is_audio) {
      await stopAudio(true);
    }
    
    // Call the existing stopHudSession function
    await stopHudSession();
  } catch (error) {
    console.error("Failed to stop session:", error);
    addSystemMessage(`❌ Error stopping session: ${error.message}`);
  }
}

// Pause session functionality
async function pauseSession() {
  if (!websocket || websocket.readyState !== WebSocket.OPEN || sessionPaused) return;
  
  sessionPaused = true;
  pauseStartTime = Date.now();
  
  // Stop audio streaming temporarily
  if (micStream) {
    micStream.getTracks().forEach(track => track.enabled = false);
  }
  
  // Send pause event to backend
  websocket.send(JSON.stringify({
    type: "pause_session",
    session_id: sessionId,
    timestamp: new Date().toISOString()
  }));
  
  // Update UI
  if (pauseBtn) pauseBtn.style.display = "none";
  if (resumeBtn) resumeBtn.style.display = "inline-block";
  addSystemMessage("⏸ Session paused");
}

// Resume session functionality
async function resumeSession() {
  if (!websocket || websocket.readyState !== WebSocket.OPEN || !sessionPaused) return;
  
  // Calculate pause duration
  const pauseDuration = (Date.now() - pauseStartTime) / 1000;
  totalPauseTime += pauseDuration;
  
  sessionPaused = false;
  
  // Resume audio streaming
  if (micStream) {
    micStream.getTracks().forEach(track => track.enabled = true);
  }
  
  // Send resume event to backend with pause duration
  websocket.send(JSON.stringify({
    type: "resume_session",
    session_id: sessionId,
    pause_duration_seconds: pauseDuration,
    timestamp: new Date().toISOString()
  }));
  
  // Update UI
  if (pauseBtn) pauseBtn.style.display = "inline-block";
  if (resumeBtn) resumeBtn.style.display = "none";
  addSystemMessage("▶ Session resumed");
}

// Helper function to clean spaces between CJK characters
// Removes spaces between Japanese/Chinese/Korean characters while preserving spaces around Latin text
function cleanCJKSpaces(text) {
  // CJK Unicode ranges: Hiragana, Katakana, Kanji, CJK Unified Ideographs, Fullwidth forms
  const cjkPattern = /[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf\uff00-\uffef]/;

  // Remove spaces between two CJK characters
  return text.replace(/(\S)\s+(?=\S)/g, (match, char1) => {
    // Get the character after the space(s)
    const nextCharMatch = text.match(new RegExp(char1 + '\\s+(.)', 'g'));
    if (nextCharMatch && nextCharMatch.length > 0) {
      const char2 = nextCharMatch[0].slice(-1);
      // If both characters are CJK, remove the space
      if (cjkPattern.test(char1) && cjkPattern.test(char2)) {
        return char1;
      }
    }
    return match;
  });
}

// Console logging functionality
function formatTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 });
}

function addConsoleEntry(type, content, data = null, emoji = null, author = null, isAudio = false) {
  // Skip audio events if checkbox is unchecked
  if (isAudio && !showAudioEventsCheckbox.checked) {
    return;
  }

  const entry = document.createElement("div");
  entry.className = `console-entry ${type}`;

  const header = document.createElement("div");
  header.className = "console-entry-header";

  const leftSection = document.createElement("div");
  leftSection.className = "console-entry-left";

  // Add emoji icon if provided
  if (emoji) {
    const emojiIcon = document.createElement("span");
    emojiIcon.className = "console-entry-emoji";
    emojiIcon.textContent = emoji;
    leftSection.appendChild(emojiIcon);
  }

  // Add expand/collapse icon
  const expandIcon = document.createElement("span");
  expandIcon.className = "console-expand-icon";
  expandIcon.textContent = data ? "▶" : "";

  const typeLabel = document.createElement("span");
  typeLabel.className = "console-entry-type";
  typeLabel.textContent = type === 'outgoing' ? '↑ Upstream' : type === 'incoming' ? '↓ Downstream' : '⚠ Error';

  leftSection.appendChild(expandIcon);
  leftSection.appendChild(typeLabel);

  // Add author badge if provided
  if (author) {
    const authorBadge = document.createElement("span");
    authorBadge.className = "console-entry-author";
    authorBadge.textContent = author;
    authorBadge.setAttribute('data-author', author);
    leftSection.appendChild(authorBadge);
  }

  const timestamp = document.createElement("span");
  timestamp.className = "console-entry-timestamp";
  timestamp.textContent = formatTimestamp();

  header.appendChild(leftSection);
  header.appendChild(timestamp);

  const contentDiv = document.createElement("div");
  contentDiv.className = "console-entry-content";
  contentDiv.textContent = content;

  entry.appendChild(header);
  entry.appendChild(contentDiv);

  // JSON details (hidden by default)
  let jsonDiv = null;
  if (data) {
    jsonDiv = document.createElement("div");
    jsonDiv.className = "console-entry-json collapsed";
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(data, null, 2);
    jsonDiv.appendChild(pre);
    entry.appendChild(jsonDiv);

    // Make entry clickable if it has data
    entry.classList.add("expandable");

    // Toggle expand/collapse on click
    entry.addEventListener("click", () => {
      const isExpanded = !jsonDiv.classList.contains("collapsed");

      if (isExpanded) {
        // Collapse
        jsonDiv.classList.add("collapsed");
        expandIcon.textContent = "▶";
        entry.classList.remove("expanded");
      } else {
        // Expand
        jsonDiv.classList.remove("collapsed");
        expandIcon.textContent = "▼";
        entry.classList.add("expanded");
      }
    });
  }

  consoleContent.appendChild(entry);
  consoleContent.scrollTop = consoleContent.scrollHeight;
}

function clearConsole() {
  consoleContent.innerHTML = '';
}

function showInterruptionBanner() {
  if (!interruptionBanner) return;
  interruptionBanner.classList.remove("hidden");
  if (interruptionBannerTimer) {
    clearTimeout(interruptionBannerTimer);
  }
  interruptionBannerTimer = setTimeout(() => {
    interruptionBanner.classList.add("hidden");
    interruptionBannerTimer = null;
  }, 3500);
}

function setSessionPausedUI(paused, reason = null) {
  isSessionPaused = paused;
  currentPauseReason = reason;

  if (paused) {
    if (audioPlayerNode) {
      audioPlayerNode.port.postMessage({ command: "endOfAudio" });
    }
    sessionPauseBanner.textContent = reason
      ? `Session paused: ${reason}`
      : "Session paused.";
    sessionPauseBanner.classList.remove("hidden");
    pauseSessionButton.disabled = true;
    resumeSessionButton.disabled = false;
    messageInput.disabled = true;
    document.getElementById("sendButton").disabled = true;
  } else {
    sessionPauseBanner.classList.add("hidden");
    pauseSessionButton.disabled = false;
    resumeSessionButton.disabled = true;
    messageInput.disabled = false;
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      document.getElementById("sendButton").disabled = false;
    }
  }
}

function sendControlEvent(type, reason = null) {
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    addSystemMessage("Cannot update session state while disconnected.");
    return;
  }
  const payload = { type };
  if (reason) payload.reason = reason;
  websocket.send(JSON.stringify(payload));
}

// Clear console button handler
if (clearConsoleBtn) {
  clearConsoleBtn.addEventListener('click', clearConsole);
}

if (startSessionBtn) {
  startSessionBtn.addEventListener("click", () => {
    void startSession();
  });
}

if (stopSessionBtn) {
  stopSessionBtn.addEventListener("click", () => {
    void stopSession();
  });
}

if (incrementRepButton) {
  incrementRepButton.addEventListener("click", () => {
    // Use new exercise tracking if exercise is active, otherwise use HUD counter
    if (currentExercise) {
      incrementExerciseReps();
    } else {
      setHudRepCount(hudRepCount + 1);
    }
  });
}

if (resetRepButton) {
  resetRepButton.addEventListener("click", () => {
    // Reset exercise tracking if exercise is active, otherwise use HUD counter
    if (currentExercise) {
      exerciseRepCount = 0;
      sendExerciseUpdate({ repCount: 0 });
      if (repCountEl) {
        repCountEl.textContent = "0";
      }
    } else {
      setHudRepCount(0);
    }
  });
}

if (pauseTimerButton) {
  pauseTimerButton.addEventListener("click", () => {
    hudTimerRunning = !hudTimerRunning;
    pauseTimerButton.textContent = hudTimerRunning ? "PAUSE" : "START";
    if (hudTimerRunning) {
      startHudTimer();
    }
  });
}

if (resetTimerButton) {
  resetTimerButton.addEventListener("click", () => {
    setHudTimerSeconds(0);
  });
}

// Add event listeners for pause/resume buttons
if (pauseBtn) {
  pauseBtn.addEventListener("click", () => {
    void pauseSession();
  });
}

if (resumeBtn) {
  resumeBtn.addEventListener("click", () => {
    void resumeSession();
  });
}

// Update connection status UI
function updateConnectionStatus(connected) {
  if (connected) {
    statusIndicator.classList.remove("disconnected");
    statusText.textContent = "Connected";
  } else {
    statusIndicator.classList.add("disconnected");
    statusText.textContent = "Disconnected";
  }

  if (startSessionBtn && startSessionBtn.style.display !== "none") {
    startSessionBtn.disabled = !connected;
  }
}

// Create a message bubble element
function createMessageBubble(text, isUser, isPartial = false) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${isUser ? "user" : "agent"}`;

  const bubbleDiv = document.createElement("div");
  bubbleDiv.className = "bubble";

  const textP = document.createElement("p");
  textP.className = "bubble-text";
  textP.textContent = text;

  // Add typing indicator for partial messages
  if (isPartial && !isUser) {
    const typingSpan = document.createElement("span");
    typingSpan.className = "typing-indicator";
    textP.appendChild(typingSpan);
  }

  bubbleDiv.appendChild(textP);
  messageDiv.appendChild(bubbleDiv);

  return messageDiv;
}

// Create an image message bubble element
function createImageBubble(imageDataUrl, isUser) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${isUser ? "user" : "agent"}`;

  const bubbleDiv = document.createElement("div");
  bubbleDiv.className = "bubble image-bubble";

  const img = document.createElement("img");
  img.src = imageDataUrl;
  img.className = "bubble-image";
  img.alt = "Captured image";

  bubbleDiv.appendChild(img);
  messageDiv.appendChild(bubbleDiv);

  return messageDiv;
}

// Update existing message bubble text
function updateMessageBubble(element, text, isPartial = false) {
  const textElement = element.querySelector(".bubble-text");

  // Remove existing typing indicator
  const existingIndicator = textElement.querySelector(".typing-indicator");
  if (existingIndicator) {
    existingIndicator.remove();
  }

  textElement.textContent = text;

  // Add typing indicator for partial messages
  if (isPartial) {
    const typingSpan = document.createElement("span");
    typingSpan.className = "typing-indicator";
    textElement.appendChild(typingSpan);
  }
}

// Add a system message
function addSystemMessage(text) {
  const messageDiv = document.createElement("div");
  messageDiv.className = "system-message";
  messageDiv.textContent = text;
  messagesDiv.appendChild(messageDiv);
  scrollToBottom();
}

// Scroll to bottom of messages
function scrollToBottom() {
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Sanitize event data for console display (replace large audio data with summary)
function sanitizeEventForDisplay(event) {
  // Deep clone the event object
  const sanitized = JSON.parse(JSON.stringify(event));

  // Check for audio data in content.parts
  if (sanitized.content && sanitized.content.parts) {
    sanitized.content.parts = sanitized.content.parts.map(part => {
      if (part.inlineData && part.inlineData.data) {
        // Calculate byte size (base64 string length / 4 * 3, roughly)
        const byteSize = Math.floor(part.inlineData.data.length * 0.75);
        return {
          ...part,
          inlineData: {
            ...part.inlineData,
            data: `(${byteSize.toLocaleString()} bytes)`
          }
        };
      }
      return part;
    });
  }

  return sanitized;
}

function isAudioRelatedEvent(adkEvent) {
  if (adkEvent.inputTranscription || adkEvent.outputTranscription) {
    return true;
  }
  if (adkEvent.content && adkEvent.content.parts) {
    return adkEvent.content.parts.some((p) => p.inlineData);
  }
  return false;
}

// WebSocket handlers
function connectWebsocket() {
  // Connect websocket
  const ws_url = getWebSocketUrl();
  websocket = new WebSocket(ws_url);

  // Handle connection open
  websocket.onopen = function () {
    console.log("WebSocket connection opened.");
    updateConnectionStatus(true);
    addSystemMessage("Connected to ADK streaming server");

    setHudSessionStatus(false);
    if (startSessionBtn && startSessionBtn.style.display !== "none") {
      startSessionBtn.disabled = false;
    }

    // Log to console
    addConsoleEntry('incoming', 'WebSocket Connected', {
      userId: userId,
      sessionId: sessionId,
      url: ws_url
    }, '🔌', 'system');

    // Enable the Send button
    document.getElementById("sendButton").disabled = false;
    setSessionPausedUI(false);
    addSubmitHandler();
  };

  // Handle incoming messages
  websocket.onmessage = function (event) {
    // Parse the incoming ADK Event
    const adkEvent = JSON.parse(event.data);
    console.log("[AGENT TO CLIENT] ", adkEvent);

    if (adkEvent.type === "session_state") {
      const status = adkEvent.status;
      if (status === "paused") {
        setSessionPausedUI(true, adkEvent.reason || "manual");
      } else if (status === "resumed" || status === "active") {
        setSessionPausedUI(false);
      } else if (status === "ended") {
        setSessionPausedUI(false);
        // Session ended - redirect to summary page
        console.log("Session ended, redirecting to summary");
        addSystemMessage("🏁 Session completed! Redirecting to summary...");
        
        // Redirect to post-session summary screen
        setTimeout(() => {
          try {
            window.location.href = `/summary?session_id=${encodeURIComponent(sessionId)}`;
          } catch (e) {
            console.error("Failed to redirect to summary:", e);
            // Fall through to local UI reset if navigation fails
            stopHudSession();
          }
        }, 2000); // 2 second delay to show message
      }
      addConsoleEntry("incoming", `Session state: ${status}`, adkEvent, "⏯️", "system");
      return;
    }

    const isAudioRelatedConsoleEvent = isAudioRelatedEvent(adkEvent);

    // Log to console panel
    let eventSummary = 'Event';
    let eventEmoji = '📨'; // Default emoji
    const author = adkEvent.author || 'system';

    if (adkEvent.turnComplete) {
      eventSummary = 'Turn Complete';
      eventEmoji = '✅';
    } else if (adkEvent.interrupted) {
      interruptionCount += 1;
      eventSummary = `Interrupted (count: ${interruptionCount})`;
      eventEmoji = '⏸️';
    } else if (adkEvent.inputTranscription) {
      // Show transcription text in summary
      const transcriptionText = adkEvent.inputTranscription.text || '';
      const truncated = transcriptionText.length > 60
        ? transcriptionText.substring(0, 60) + '...'
        : transcriptionText;
      eventSummary = `Input Transcription: "${truncated}"`;
      eventEmoji = '📝';
    } else if (adkEvent.outputTranscription) {
      // Show transcription text in summary
      const transcriptionText = adkEvent.outputTranscription.text || '';
      const truncated = transcriptionText.length > 60
        ? transcriptionText.substring(0, 60) + '...'
        : transcriptionText;
      eventSummary = `Output Transcription: "${truncated}"`;
      eventEmoji = '📝';
    } else if (adkEvent.usageMetadata) {
      // Show token usage information
      const usage = adkEvent.usageMetadata;
      const promptTokens = usage.promptTokenCount || 0;
      const responseTokens = usage.candidatesTokenCount || 0;
      const totalTokens = usage.totalTokenCount || 0;
      eventSummary = `Token Usage: ${totalTokens.toLocaleString()} total (${promptTokens.toLocaleString()} prompt + ${responseTokens.toLocaleString()} response)`;
      eventEmoji = '📊';
    } else if (adkEvent.content && adkEvent.content.parts) {
      const hasText = adkEvent.content.parts.some(p => p.text);
      const hasAudio = adkEvent.content.parts.some(p => p.inlineData);
      const hasExecutableCode = adkEvent.content.parts.some(p => p.executableCode);
      const hasCodeExecutionResult = adkEvent.content.parts.some(p => p.codeExecutionResult);

      if (hasExecutableCode) {
        // Show executable code
        const codePart = adkEvent.content.parts.find(p => p.executableCode);
        if (codePart && codePart.executableCode) {
          const code = codePart.executableCode.code || '';
          const language = codePart.executableCode.language || 'unknown';
          const truncated = code.length > 60
            ? code.substring(0, 60).replace(/\n/g, ' ') + '...'
            : code.replace(/\n/g, ' ');
          eventSummary = `Executable Code (${language}): ${truncated}`;
          eventEmoji = '💻';
        }
      }

      if (hasCodeExecutionResult) {
        // Show code execution result
        const resultPart = adkEvent.content.parts.find(p => p.codeExecutionResult);
        if (resultPart && resultPart.codeExecutionResult) {
          const outcome = resultPart.codeExecutionResult.outcome || 'UNKNOWN';
          const output = resultPart.codeExecutionResult.output || '';
          const truncatedOutput = output.length > 60
            ? output.substring(0, 60).replace(/\n/g, ' ') + '...'
            : output.replace(/\n/g, ' ');
          eventSummary = `Code Execution Result (${outcome}): ${truncatedOutput}`;
          eventEmoji = outcome === 'OUTCOME_OK' ? '✅' : '❌';
        }
      }

      if (hasText) {
        // Show text preview in summary
        const textPart = adkEvent.content.parts.find(p => p.text);
        if (textPart && textPart.text) {
          const text = textPart.text;
          const truncated = text.length > 80
            ? text.substring(0, 80) + '...'
            : text;
          eventSummary = `Text: "${truncated}"`;
          eventEmoji = '💭';
        } else {
          eventSummary = 'Text Response';
          eventEmoji = '💭';
        }
      }

      if (hasAudio) {
        // Extract audio info for summary
        const audioPart = adkEvent.content.parts.find(p => p.inlineData);
        if (audioPart && audioPart.inlineData) {
          const mimeType = audioPart.inlineData.mimeType || 'unknown';
          const dataLength = audioPart.inlineData.data ? audioPart.inlineData.data.length : 0;
          // Base64 string length / 4 * 3 gives approximate bytes
          const byteSize = Math.floor(dataLength * 0.75);
          eventSummary = `Audio Response: ${mimeType} (${byteSize.toLocaleString()} bytes)`;
          eventEmoji = '🔊';
        } else {
          eventSummary = 'Audio Response';
          eventEmoji = '🔊';
        }

        // Log audio event with isAudio flag (filtered by checkbox)
        const sanitizedEvent = sanitizeEventForDisplay(adkEvent);
        addConsoleEntry('incoming', eventSummary, sanitizedEvent, eventEmoji, author, true);
      }
    }

    // Create a sanitized version for console display (replace large audio data with summary)
    // Skip if already logged as audio event above
    const isAudioOnlyEvent = adkEvent.content && adkEvent.content.parts &&
      adkEvent.content.parts.some(p => p.inlineData) &&
      !adkEvent.content.parts.some(p => p.text);
    if (!isAudioOnlyEvent) {
      const sanitizedEvent = sanitizeEventForDisplay(adkEvent);
      addConsoleEntry('incoming', eventSummary, sanitizedEvent, eventEmoji, author, isAudioRelatedConsoleEvent);
    }

    // Handle turn complete event
    if (adkEvent.turnComplete === true) {
      // Remove typing indicator from current message
      if (currentBubbleElement) {
        const textElement = currentBubbleElement.querySelector(".bubble-text");
        const typingIndicator = textElement.querySelector(".typing-indicator");
        if (typingIndicator) {
          typingIndicator.remove();
        }
      }
      // Remove typing indicator from current output transcription
      if (currentOutputTranscriptionElement) {
        const textElement = currentOutputTranscriptionElement.querySelector(".bubble-text");
        const typingIndicator = textElement.querySelector(".typing-indicator");
        if (typingIndicator) {
          typingIndicator.remove();
        }
      }
      currentMessageId = null;
      currentBubbleElement = null;
      currentOutputTranscriptionId = null;
      currentOutputTranscriptionElement = null;
      inputTranscriptionFinished = false; // Reset for next turn
      hasOutputTranscriptionInTurn = false; // Reset for next turn
      return;
    }

    // Handle interrupted event
    if (adkEvent.interrupted === true) {
      showInterruptionBanner();
      addSystemMessage("Safety correction: coach interrupted for immediate feedback.");
      addConsoleEntry('incoming', 'Interruption detected', {
        interruptionCount: interruptionCount,
        reason: 'model interruption event',
      }, '⏸️', author);

      // Stop audio playback if it's playing
      if (audioPlayerNode) {
        audioPlayerNode.port.postMessage({ command: "endOfAudio" });
      }

      // Keep the partial message but mark it as interrupted
      if (currentBubbleElement) {
        const textElement = currentBubbleElement.querySelector(".bubble-text");

        // Remove typing indicator
        const typingIndicator = textElement.querySelector(".typing-indicator");
        if (typingIndicator) {
          typingIndicator.remove();
        }

        // Add interrupted marker
        currentBubbleElement.classList.add("interrupted");
      }

      // Keep the partial output transcription but mark it as interrupted
      if (currentOutputTranscriptionElement) {
        const textElement = currentOutputTranscriptionElement.querySelector(".bubble-text");

        // Remove typing indicator
        const typingIndicator = textElement.querySelector(".typing-indicator");
        if (typingIndicator) {
          typingIndicator.remove();
        }

        // Add interrupted marker
        currentOutputTranscriptionElement.classList.add("interrupted");
      }

      // Reset state so new content creates a new bubble
      currentMessageId = null;
      currentBubbleElement = null;
      currentOutputTranscriptionId = null;
      currentOutputTranscriptionElement = null;
      inputTranscriptionFinished = false; // Reset for next turn
      hasOutputTranscriptionInTurn = false; // Reset for next turn
      return;
    }

    // Handle input transcription (user's spoken words)
    if (adkEvent.inputTranscription && adkEvent.inputTranscription.text) {
      const transcriptionText = adkEvent.inputTranscription.text;
      const isFinished = adkEvent.inputTranscription.finished;

      if (transcriptionText) {
        // Ignore late-arriving transcriptions after we've finished for this turn
        if (inputTranscriptionFinished) {
          return;
        }

        if (currentInputTranscriptionId == null) {
          // Create new transcription bubble
          currentInputTranscriptionId = Math.random().toString(36).substring(7);
          // Clean spaces between CJK characters
          const cleanedText = cleanCJKSpaces(transcriptionText);
          currentInputTranscriptionElement = createMessageBubble(cleanedText, true, !isFinished);
          currentInputTranscriptionElement.id = currentInputTranscriptionId;

          // Add a special class to indicate it's a transcription
          currentInputTranscriptionElement.classList.add("transcription");

          messagesDiv.appendChild(currentInputTranscriptionElement);
        } else {
          // Update existing transcription bubble only if model hasn't started responding
          // This prevents late partial transcriptions from overwriting complete ones
          if (currentOutputTranscriptionId == null && currentMessageId == null) {
            if (isFinished) {
              // Final transcription contains the complete text, replace entirely
              const cleanedText = cleanCJKSpaces(transcriptionText);
              updateMessageBubble(currentInputTranscriptionElement, cleanedText, false);
            } else {
              // Partial transcription - append to existing text
              const existingText = currentInputTranscriptionElement.querySelector(".bubble-text").textContent;
              // Remove typing indicator if present
              const cleanText = existingText.replace(/\.\.\.$/, '');
              // Clean spaces between CJK characters before updating
              const accumulatedText = cleanCJKSpaces(cleanText + transcriptionText);
              updateMessageBubble(currentInputTranscriptionElement, accumulatedText, true);
            }
          }
        }

        // If transcription is finished, reset the state and mark as complete
        if (isFinished) {
          currentInputTranscriptionId = null;
          currentInputTranscriptionElement = null;
          inputTranscriptionFinished = true; // Prevent duplicate bubbles from late events
        }

        scrollToBottom();
      }
    }

    // Handle output transcription (model's spoken words)
    if (adkEvent.outputTranscription && adkEvent.outputTranscription.text) {
      const transcriptionText = adkEvent.outputTranscription.text;
      const isFinished = adkEvent.outputTranscription.finished;
      hasOutputTranscriptionInTurn = true;

      // Auto-detect exercises and reps from AI speech
      if (transcriptionText) {
        detectExerciseType(transcriptionText);
        if (currentExercise) {
          detectFormCorrections(transcriptionText);
          detectRepCounting(transcriptionText);
        }
      }

      if (transcriptionText) {
        // Finalize any active input transcription when server starts responding
        if (currentInputTranscriptionId != null && currentOutputTranscriptionId == null) {
          // This is the first output transcription - finalize input transcription
          const textElement = currentInputTranscriptionElement.querySelector(".bubble-text");
          const typingIndicator = textElement.querySelector(".typing-indicator");
          if (typingIndicator) {
            typingIndicator.remove();
          }
          // Reset input transcription state so next user input creates new balloon
          currentInputTranscriptionId = null;
          currentInputTranscriptionElement = null;
          inputTranscriptionFinished = true; // Prevent duplicate bubbles from late events
        }

        if (currentOutputTranscriptionId == null) {
          // Create new transcription bubble for agent
          currentOutputTranscriptionId = Math.random().toString(36).substring(7);
          currentOutputTranscriptionElement = createMessageBubble(transcriptionText, false, !isFinished);
          currentOutputTranscriptionElement.id = currentOutputTranscriptionId;

          // Add a special class to indicate it's a transcription
          currentOutputTranscriptionElement.classList.add("transcription");

          messagesDiv.appendChild(currentOutputTranscriptionElement);
        } else {
          // Update existing transcription bubble
          if (isFinished) {
            // Final transcription contains the complete text, replace entirely
            updateMessageBubble(currentOutputTranscriptionElement, transcriptionText, false);
          } else {
            // Partial transcription - append to existing text
            const existingText = currentOutputTranscriptionElement.querySelector(".bubble-text").textContent;
            // Remove typing indicator if present
            const cleanText = existingText.replace(/\.\.\.$/, '');
            updateMessageBubble(currentOutputTranscriptionElement, cleanText + transcriptionText, true);
          }
        }

        // If transcription is finished, reset the state
        if (isFinished) {
          currentOutputTranscriptionId = null;
          currentOutputTranscriptionElement = null;
        }

        scrollToBottom();
      }
    }

    // Handle content events (text or audio)
    if (adkEvent.content && adkEvent.content.parts) {
      const parts = adkEvent.content.parts;

      // Finalize any active input transcription when server starts responding with content
      if (currentInputTranscriptionId != null && currentMessageId == null && currentOutputTranscriptionId == null) {
        // This is the first content event - finalize input transcription
        const textElement = currentInputTranscriptionElement.querySelector(".bubble-text");
        const typingIndicator = textElement.querySelector(".typing-indicator");
        if (typingIndicator) {
          typingIndicator.remove();
        }
        // Reset input transcription state so next user input creates new balloon
        currentInputTranscriptionId = null;
        currentInputTranscriptionElement = null;
        inputTranscriptionFinished = true; // Prevent duplicate bubbles from late events
      }

      for (const part of parts) {
        // Handle inline data (audio)
        if (part.inlineData) {
          const mimeType = part.inlineData.mimeType;
          const data = part.inlineData.data;

          if (mimeType && mimeType.startsWith("audio/pcm") && audioPlayerNode) {
            audioPlayerNode.port.postMessage(base64ToArray(data));
          }
        }

        // Handle text
        if (part.text) {
          // Skip thinking/reasoning text from chat bubbles (shown in event console)
          if (part.thought) {
            continue;
          }

          // Skip final aggregated content when output transcription already
          // delivered the response (prevents duplicate thinking text replay)
          if (!adkEvent.partial && hasOutputTranscriptionInTurn) {
            continue;
          }

          // Detect form corrections in AI coach responses
          if (currentExercise && part.text) {
            detectFormCorrections(part.text);
            detectRepCounting(part.text);
          }
          
          // Auto-detect exercises from AI coach responses (even if no exercise is active)
          if (part.text) {
            detectExerciseType(part.text);
          }

          // Add a new message bubble for a new turn
          if (currentMessageId == null) {
            currentMessageId = Math.random().toString(36).substring(7);
            currentBubbleElement = createMessageBubble(part.text, false, true);
            currentBubbleElement.id = currentMessageId;
            messagesDiv.appendChild(currentBubbleElement);
          } else {
            // Update the existing message bubble with accumulated text
            const existingText = currentBubbleElement.querySelector(".bubble-text").textContent;
            // Remove the "..." if present
            const cleanText = existingText.replace(/\.\.\.$/, '');
            updateMessageBubble(currentBubbleElement, cleanText + part.text, true);
          }

          // Scroll down to the bottom of the messagesDiv
          scrollToBottom();
        }
      }
    }
  };

  // Handle connection close
  websocket.onclose = function (event) {
    console.log("WebSocket closed:", event.code, event.reason);
    updateConnectionStatus(false);
    setSessionPausedUI(false);
    document.getElementById("sendButton").disabled = true;
    if (is_audio || isAudioStarting) {
      void stopAudio(true);
    }
    
    // Check if this was a service unavailable error
    if (event.reason && event.reason.includes("service is currently unavailable")) {
      addSystemMessage("🔴 Google AI service is currently unavailable. Please try again later.");
      addSystemMessage("💡 This is a Google API issue, not a problem with your setup.");
      return; // Don't try to reconnect if service is down
    }
    
    // Check if this was an active session that ended unexpectedly
    if (event.code !== 1000 && sessionId && is_audio) {
      console.log("Active session ended unexpectedly, checking for summary...");
      addSystemMessage("🔌 Connection lost. Checking for session summary...");
      
      // Wait a moment for summary to be created, then redirect
      setTimeout(() => {
        try {
          window.location.href = `/summary?session_id=${encodeURIComponent(sessionId)}`;
        } catch (e) {
          console.error("Failed to redirect to summary:", e);
          addSystemMessage("❌ Session ended. Summary may not be available.");
        }
      }, 3000);
    } else {
      addSystemMessage("Connection closed. Reconnecting in 5 seconds...");
      void connectWebSocket();
    }
  };

  websocket.onerror = function (e) {
    console.log("WebSocket error: ", e);
    updateConnectionStatus(false);

    // Log to console
    addConsoleEntry('error', 'WebSocket Error', {
      error: e.type,
      message: 'Connection error occurred'
    }, '⚠️', 'system');
  };
}
connectWebsocket();

// Add submit handler to the form
function addSubmitHandler() {
  messageForm.onsubmit = function (e) {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (message) {
      // Add user message bubble
      const userBubble = createMessageBubble(message, true, false);
      messagesDiv.appendChild(userBubble);
      scrollToBottom();

      // Clear input
      messageInput.value = "";

      // Send message to server
      sendMessage(message);
      console.log("[CLIENT TO AGENT] " + message);
    }
    return false;
  };
}

// Send a message to the server as JSON
function sendMessage(message) {
  if (isSessionPaused) {
    addSystemMessage("Session is paused. Click Resume Session before sending messages.");
    return;
  }
  if (websocket && websocket.readyState == WebSocket.OPEN) {
    const jsonMessage = JSON.stringify({
      type: "text",
      text: message
    });
    websocket.send(jsonMessage);

    // Log to console panel
    addConsoleEntry('outgoing', 'User Message: ' + message, null, '💬', 'user');
  }
}

// Exercise tracking functions
function sendExerciseUpdate(exerciseData) {
  if (isSessionPaused || !websocket || websocket.readyState !== WebSocket.OPEN) {
    return;
  }
  
  const exerciseEvent = {
    type: "exercise_update",
    exercise_id: exerciseData.exerciseId || currentExercise,
    rep_count: exerciseData.repCount || exerciseRepCount,
    form_corrections: exerciseData.formCorrections || formCorrections,
    exercise_type: exerciseData.exerciseType || currentExercise
  };
  
  websocket.send(JSON.stringify(exerciseEvent));
  addConsoleEntry('outgoing', 'Exercise Update', exerciseEvent, '🏋️', 'user');
}

function sendSessionEnd() {
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    return;
  }
  
  const endEvent = {
    type: "end",
    summary: {
      exercise_type: currentExercise || "unknown",
      rep_count: exerciseRepCount || 0,
      form_corrections: formCorrections || [],
      session_goal: sessionGoal || "complete workout"
    }
  };
  
  websocket.send(JSON.stringify(endEvent));
  addConsoleEntry('outgoing', 'Session End', endEvent, '🏁', 'user');
}

function startExercise(exerciseType, goal = null) {
  currentExercise = exerciseType;
  exerciseRepCount = 0;
  formCorrections = [];
  sessionGoal = goal;
  
  sendExerciseUpdate({
    exerciseId: exerciseType,
    exerciseType: exerciseType,
    repCount: 0,
    formCorrections: []
  });
  
  // Update session status display
  if (sessionStatusText) {
    sessionStatusText.textContent = `● ${exerciseType.toUpperCase()}`;
  }
  
  addSystemMessage(`Started exercise: ${exerciseType}`);
}

function incrementExerciseReps() {
  exerciseRepCount++;
  sendExerciseUpdate({
    repCount: exerciseRepCount
  });
  
  // Update UI rep counter if exists
  if (repCountEl) {
    repCountEl.textContent = exerciseRepCount;
  }
}

function addFormCorrection(correction) {
  formCorrections.push(correction);
  sendExerciseUpdate({
    formCorrections: formCorrections
  });
}

function detectFormCorrections(text) {
  // Common form correction patterns
  const correctionPatterns = [
    /keep your (back|chest|head|neck) (straight|flat|aligned|neutral)/gi,
    /lower your (chest|hips|body)/gi,
    /raise your (hips|chest|head)/gi,
    /bend your (knees|elbows) (more|less)/gi,
    /straighten your (back|arms|legs)/gi,
    /engage your (core|abs|glutes)/gi,
    /don't (round|arch) your (back|lower back)/gi,
    /maintain (proper|good) form/gi,
    /form check/gi
  ];
  
  for (const pattern of correctionPatterns) {
    if (pattern.test(text)) {
      // Extract the correction phrase
      const match = text.match(pattern)[0];
      const correction = match.toLowerCase();
      
      // Avoid duplicates
      if (!formCorrections.includes(correction)) {
        addFormCorrection(correction);
        addSystemMessage(`Form correction noted: ${correction}`);
      }
      break; // Only take one correction per message to avoid spam
    }
  }
}

function detectExerciseType(text) {
  // Exercise detection patterns - match actual exercise library names and common phrases
  // More specific patterns first to avoid conflicts
  const exercisePatterns = [
    { exercise: 'mountain_climber', patterns: [/mountain.?climber/gi] },
    { exercise: 'side_plank', patterns: [/side.?plank/gi] },
    { exercise: 'push_up', patterns: [/push.?up/gi, /pushup/gi, /push.?ups?/gi] },
    { exercise: 'air_squat', patterns: [/squat/gi, /squatting/gi, /air.?squat/gi, /air squat/gi] },
    { exercise: 'plank', patterns: [/plank/gi, /planking/gi, /plank.?hold/gi, /front.?plank/gi] },
    { exercise: 'jumping_jack', patterns: [/jumping.?jack/gi, /jumping jack/gi] },
    { exercise: 'reverse_lunge', patterns: [/lunge/gi, /lunging/gi, /reverse.?lunge/gi] },
    { exercise: 'dead_bug', patterns: [/dead.?bug/gi] },
    { exercise: 'bird_dog', patterns: [/bird.?dog/gi] },
    { exercise: 'good_morning', patterns: [/good.?morning/gi, /hip.?hinge/gi] },
    { exercise: 'glute_bridge', patterns: [/glute.?bridge/gi, /bridge/gi] },
    { exercise: 'wall_sit', patterns: [/wall.?sit/gi] },
    { exercise: 'calf_raise', patterns: [/calf.?raise/gi] },
    { exercise: 'superman_hold', patterns: [/superman/gi] },
    { exercise: 'step_jack', patterns: [/step.?jack/gi] },
    { exercise: 'chair_squat', patterns: [/chair.?squat/gi] }
  ];
  
  for (const { exercise, patterns } of exercisePatterns) {
    for (const pattern of patterns) {
      if (pattern.test(text)) {
        // Only start new exercise if different from current
        if (currentExercise !== exercise) {
          startExercise(exercise, `coach-guided ${exercise.replace('_', ' ')}`);
          addSystemMessage(`Exercise detected from coach: ${exercise.replace('_', ' ').toUpperCase()}`);
          return true;
        }
        return false;
      }
    }
  }
  return false;
}

function detectRepCounting(text) {
  if (!currentExercise) return false;
  
  // Rep counting patterns - what coaches might say
  const repPatterns = [
    /that(?:'s| is)? (\d+)/gi,
    /good (\d+)/gi,
    /nice (\d+)/gi,
    /great (\d+)/gi,
    /perfect (\d+)/gi,
    /(\d+) (reps?|more)/gi,
    /rep (\d+)/gi,
    /you did (\d+)/gi,
    /you have (\d+)/gi,
    /that was (\d+)/gi,
    /(\d+) (was|were) good/gi,
    /let's do (\d+)/gi,
    /do (\d+) more/gi
  ];
  
  for (const pattern of repPatterns) {
    const match = text.match(pattern);
    if (match) {
      const repCount = parseInt(match[1]);
      if (repCount > 0 && repCount !== exerciseRepCount) {
        exerciseRepCount = repCount;
        sendExerciseUpdate({ repCount: exerciseRepCount });
        
        // Update UI
        if (repCountEl) {
          repCountEl.textContent = exerciseRepCount;
        }
        
        addSystemMessage(`Rep count updated: ${exerciseRepCount}`);
        return true;
      }
    }
  }
  return false;
}

// Decode Base64 data to Array
// Handles both standard base64 and base64url encoding
function base64ToArray(base64) {
  // Convert base64url to standard base64
  // Replace URL-safe characters: - with +, _ with /
  let standardBase64 = base64.replace(/-/g, '+').replace(/_/g, '/');

  // Add padding if needed
  while (standardBase64.length % 4) {
    standardBase64 += '=';
  }

  const binaryString = window.atob(standardBase64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Camera handling
 */

const cameraButton = document.getElementById("cameraButton");
const cameraPreview = document.getElementById("cameraPreview");
const cameraPreviewBg = document.getElementById("cameraPreviewBg");
const videoPreviewPanel = document.getElementById("videoPreviewPanel");

const VIDEO_FRAME_INTERVAL_MS = 1000;
const VIDEO_JPEG_QUALITY = 0.7;
const VIDEO_COACH_INTERVAL_MS = 10000;
const VIDEO_DIMENSION_IDEAL = 768;

let isVideoStreaming = false;
let videoStream = null;
let videoFrameTimer = null;
let videoCoachTimer = null;
let videoCanvas = null;
let videoCtx = null;
let isFrameEncodeInFlight = false;
let videoFrameCount = 0;

async function startVideoStream() {
  if (isVideoStreaming) return;
  if (isSessionPaused) {
    addSystemMessage("Session is paused. Resume session before starting video.");
    return;
  }
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    addSystemMessage("WebSocket is disconnected. Wait for reconnect before starting video.");
    return;
  }

  try {
    try {
      videoStream = await getUserMediaCompat({
        video: {
          width: { ideal: VIDEO_DIMENSION_IDEAL },
          height: { ideal: VIDEO_DIMENSION_IDEAL },
          facingMode: "user",
        },
        audio: false,
      });
    } catch (e) {
      videoStream = await getUserMediaCompat({
        video: { facingMode: "user" },
        audio: false,
      });
    }

    cameraPreview.srcObject = videoStream;
    if (cameraPreviewBg) {
      cameraPreviewBg.srcObject = videoStream;
    }
    await cameraPreview.play();
    if (cameraPreviewBg) {
      try {
        await cameraPreviewBg.play();
      } catch (e) {
        // ignore autoplay issues for the background layer
      }
    }

    if (!videoCanvas) {
      videoCanvas = document.createElement("canvas");
    }
    videoCtx = videoCanvas.getContext("2d");

    isVideoStreaming = true;
    videoPreviewPanel.classList.remove("hidden");
    cameraButton.textContent = "🛑 Stop Video";

    videoFrameTimer = setInterval(sendCurrentVideoFrame, VIDEO_FRAME_INTERVAL_MS);
    videoCoachTimer = setInterval(sendPeriodicCoachPrompt, VIDEO_COACH_INTERVAL_MS);
    sendPeriodicCoachPrompt();

    addSystemMessage("Video stream started (1 FPS).");
    addConsoleEntry("outgoing", "Video Stream Started", {
      fps: 1,
      imageFormat: "image/jpeg",
      quality: VIDEO_JPEG_QUALITY,
      coachIntervalMs: VIDEO_COACH_INTERVAL_MS
    }, "🎥", "system");
  } catch (error) {
    console.error("Error starting video stream:", error);
    addSystemMessage(`Failed to start video: ${error.message}`);
    addConsoleEntry("error", "Video stream failed", {
      error: error.message,
      name: error.name
    }, "⚠️", "system");
    void stopVideoStream(true);
  }
}

async function stopVideoStream(silent = false) {
  isVideoStreaming = false;
  isFrameEncodeInFlight = false;
  videoFrameCount = 0;

  if (videoFrameTimer) {
    clearInterval(videoFrameTimer);
    videoFrameTimer = null;
  }
  if (videoCoachTimer) {
    clearInterval(videoCoachTimer);
    videoCoachTimer = null;
  }

  if (videoStream) {
    videoStream.getTracks().forEach((track) => track.stop());
    videoStream = null;
  }

  if (cameraPreview) {
    cameraPreview.srcObject = null;
  }

  videoPreviewPanel.classList.add("hidden");
  cameraButton.textContent = "🎥 Start Video";

  if (!silent) {
    addSystemMessage("Video stream stopped.");
    addConsoleEntry("outgoing", "Video Stream Stopped", {
      status: "stopped"
    }, "🛑", "system");
  }
}

function toggleVideoStream() {
  if (isSessionPaused) {
    addSystemMessage("Session is paused. Resume session before changing video state.");
    return;
  }
  if (isVideoStreaming) {
    void stopVideoStream();
  } else {
    void startVideoStream();
  }
}

function sendPeriodicCoachPrompt() {
  websocket.send(JSON.stringify({
    type: "text",
    text: "Video stream is active. Give one short form correction if needed."
  }));
}

function sendCurrentVideoFrame() {
  if (isSessionPaused || !isVideoStreaming || !videoStream || !videoCtx || !cameraPreview) return;
  if (!websocket || websocket.readyState !== WebSocket.OPEN) return;
  if (isFrameEncodeInFlight) return;
  if (!cameraPreview.videoWidth || !cameraPreview.videoHeight) return;

  isFrameEncodeInFlight = true;

  videoCanvas.width = cameraPreview.videoWidth;
  videoCanvas.height = cameraPreview.videoHeight;
  videoCtx.drawImage(cameraPreview, 0, 0, videoCanvas.width, videoCanvas.height);

  videoCanvas.toBlob((blob) => {
    try {
      if (!blob || !isVideoStreaming || !websocket || websocket.readyState !== WebSocket.OPEN) {
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        const dataUrl = reader.result;
        if (typeof dataUrl !== "string") {
          isFrameEncodeInFlight = false;
          return;
        }

        const base64Data = dataUrl.split(",")[1];
        websocket.send(JSON.stringify({
          type: "video",
          data: base64Data,
          mimeType: "image/jpeg",
        }));

        videoFrameCount += 1;
        // throttle console logging to avoid flooding
        if (videoFrameCount % 10 === 0) {
          addConsoleEntry("outgoing", "Video frames streaming", {
            framesSent: videoFrameCount,
            fps: 1
          }, "🎞️", "user");
        }
        isFrameEncodeInFlight = false;
      };
      reader.onerror = () => {
        isFrameEncodeInFlight = false;
      };
      reader.readAsDataURL(blob);
    } catch (err) {
      console.warn("Failed to encode/send video frame", err);
      isFrameEncodeInFlight = false;
    }
  }, "image/jpeg", VIDEO_JPEG_QUALITY);
}

cameraButton.addEventListener("click", toggleVideoStream);
pauseSessionButton.addEventListener("click", () => {
  sendControlEvent("pause", "manual_pause");
});
resumeSessionButton.addEventListener("click", () => {
  sendControlEvent("resume");
});

/**
 * Audio handling
 */

let audioPlayerNode;
let audioPlayerContext;
let audioRecorderNode;
let audioRecorderContext;
let micStream;
let mediaStream;
let isAudioStarting = false;

// Import the audio worklets
import { startAudioPlayerWorklet } from "./audio-player.js";
import { startAudioRecorderWorklet } from "./audio-recorder.js";

// Start audio
function startAudio() {
  // Start audio output
  const outputPromise = startAudioPlayerWorklet().then(([node, ctx]) => {
    audioPlayerNode = node;
    audioPlayerContext = ctx;
  });
  // Start audio input
  const inputPromise = startAudioRecorderWorklet(audioRecorderHandler).then(
    ([node, ctx, stream]) => {
      audioRecorderNode = node;
      audioRecorderContext = ctx;
      micStream = stream; // This should set the global micStream
      console.log("Audio input started, micStream tracks:", micStream?.getTracks().length);
    }
  );
  return Promise.all([outputPromise, inputPromise]);
}

async function stopAudio(silent = false) {
  is_audio = false;
  isAudioStarting = false;

  try {
    if (audioRecorderNode) {
      audioRecorderNode.port.onmessage = null;
      audioRecorderNode.disconnect();
    }
  } catch (e) {
    console.warn("Error disconnecting recorder node:", e);
  }

  try {
    if (audioPlayerNode) {
      audioPlayerNode.port.postMessage({ command: "endOfAudio" });
      audioPlayerNode.disconnect();
    }
  } catch (e) {
    console.warn("Error disconnecting player node:", e);
  }

  try {
    if (micStream) {
      micStream.getTracks().forEach((track) => track.stop());
    }
  } catch (e) {
    console.warn("Error stopping microphone tracks:", e);
  }

  try {
    if (audioRecorderContext && audioRecorderContext.state !== "closed") {
      await audioRecorderContext.close();
    }
  } catch (e) {
    console.warn("Error closing recorder context:", e);
  }

  try {
    if (audioPlayerContext && audioPlayerContext.state !== "closed") {
      await audioPlayerContext.close();
    }
  } catch (e) {
    console.warn("Error closing player context:", e);
  }

  audioRecorderNode = null;
  audioPlayerNode = null;
  audioRecorderContext = null;
  audioPlayerContext = null;
  micStream = null;

  if (!silent) {
    addSystemMessage("Audio mode stopped");
    addConsoleEntry('outgoing', 'Audio Mode Stopped', {
      status: 'Audio worklets stopped',
      message: 'Microphone disabled'
    }, '🛑', 'system');
  }
}

// Audio recorder handler
function audioRecorderHandler(pcmData) {
  // Log occasionally to see if audio is being processed
  if (!audioRecorderHandler.logCounter) audioRecorderHandler.logCounter = 0;
  audioRecorderHandler.logCounter++;
  
  if (audioRecorderHandler.logCounter % 100 === 0) {
    console.log("Audio data received, bytes:", pcmData.byteLength, "is_audio:", is_audio, "session_paused:", isSessionPaused);
  }
  
  if (websocket && websocket.readyState === WebSocket.OPEN && is_audio && !isSessionPaused) {
    // Send audio as binary WebSocket frame (more efficient than base64 JSON)
    websocket.send(pcmData);
    console.log("[CLIENT TO AGENT] Sent audio chunk: %s bytes", pcmData.byteLength);

    // Log to console panel (optional, can be noisy with frequent audio chunks)
    // addConsoleEntry('outgoing', `Audio chunk: ${pcmData.byteLength} bytes`);
  }
}

async function getUserMediaCompat(constraints) {
  if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function") {
    return navigator.mediaDevices.getUserMedia(constraints);
  }

  const legacyGetUserMedia =
    navigator.getUserMedia ||
    navigator.webkitGetUserMedia ||
    navigator.mozGetUserMedia ||
    navigator.msGetUserMedia;

  if (!legacyGetUserMedia) {
    throw new Error(
      "getUserMedia unavailable. Use latest Chrome/Edge and open via http://localhost:8000."
    );
  }

  return new Promise((resolve, reject) => {
    legacyGetUserMedia.call(navigator, constraints, resolve, reject);
  });
}

window.addEventListener("beforeunload", () => {
  if (isVideoStreaming) {
    void stopVideoStream(true);
  }
  if (is_audio || isAudioStarting) {
    void stopAudio(true);
  }
});

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeApp);
} else {
  initializeApp();
}
