import { FormEvent, PointerEvent as ReactPointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import WebcamFeed from "../components/WebcamFeed";
import TimerWidget from "../components/TimerWidget";
import { useLiveSession } from "../hooks/useLiveSession";

type TimerMode = "countdown" | "unknown";

type Point = {
  x: number;
  y: number;
};

const correctionKeywords = ["knee", "hip", "back", "elbow", "shoulder", "form", "balance"];

export default function SessionPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const videoWrapperRef = useRef<HTMLDivElement>(null);
  const [wsUrl, setWsUrl] = useState("http://localhost:8000");
  const [sessionId, setSessionId] = useState("demo-session");
  const [userId, setUserId] = useState("demo-parent");
  const [sessionGoal, setSessionGoal] = useState("General coaching");
  const [timerMode, setTimerMode] = useState<TimerMode>("unknown");
  const [countdownMinutes, setCountdownMinutes] = useState(5);
  const [showSketch, setShowSketch] = useState(true);
  const [overlayPoints, setOverlayPoints] = useState<Point[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [historyInput, setHistoryInput] = useState("");
  const [history, setHistory] = useState(["air_squat", "push_up"]);
  const [containerSize, setContainerSize] = useState({ width: 640, height: 360 });

  const { state, start, stop, sendText } = useLiveSession();

  const connectedLabel = state.connected ? "Connected" : "Disconnected";

  const correctionActive = useMemo(
    () =>
      state.transcripts.some((line) =>
        correctionKeywords.some((keyword) => line.toLowerCase().includes(keyword))
      ),
    [state.transcripts]
  );

  useEffect(() => {
    const resize = () => {
      const bounds = videoWrapperRef.current?.getBoundingClientRect();
      if (bounds) {
        setContainerSize({ width: bounds.width, height: bounds.height });
      }
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    const canvas = overlayRef.current;
    if (!canvas || !showSketch) {
      return undefined;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;
    canvas.width = containerSize.width;
    canvas.height = containerSize.height;

    let frame: number;
    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (overlayPoints.length > 1) {
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        ctx.beginPath();
        overlayPoints.forEach((point, index) => {
          const alpha = (index + 1) / overlayPoints.length;
          ctx.strokeStyle = correctionActive
            ? `rgba(255,107,107,${0.5 + alpha / 2})`
            : `rgba(126,249,255,${0.4 + alpha / 2})`;
          ctx.lineWidth = 2 + alpha * 3;
          if (index === 0) {
            ctx.moveTo(point.x, point.y);
          } else {
            ctx.lineTo(point.x, point.y);
          }
        });
        ctx.stroke();
      }
      if (correctionActive) {
        ctx.fillStyle = "rgba(255,107,107,0.25)";
        const radius = Math.min(canvas.width, canvas.height) * 0.25;
        ctx.beginPath();
        ctx.ellipse(canvas.width / 2, canvas.height / 2, radius, radius, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      frame = window.requestAnimationFrame(render);
    };
    frame = window.requestAnimationFrame(render);
    return () => window.cancelAnimationFrame(frame);
  }, [overlayPoints, containerSize, correctionActive, showSketch]);

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!showSketch) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      const x = event.clientX - bounds.left;
      const y = event.clientY - bounds.top;
      setOverlayPoints((prev) => {
        const next = [...prev, { x, y }];
        return next.length > 120 ? next.slice(next.length - 120) : next;
      });
    },
    [showSketch]
  );

  const handleStart = useCallback(() => {
    if (!videoRef.current) return;
    void start({
      sessionId,
      userId,
      wsUrl,
      sessionGoal,
      timeRemainingSec: timerMode === "countdown" ? countdownMinutes * 60 : undefined,
      videoElement: videoRef.current,
      parentId: "parent",
    });
  }, [countdownMinutes, sessionGoal, sessionId, start, timerMode, userId, wsUrl]);

  const handleSend = useCallback(
    (event: FormEvent) => {
      event.preventDefault();
      if (!inputMessage.trim()) return;
      sendText(inputMessage.trim());
      setInputMessage("");
    },
    [inputMessage, sendText]
  );

  const handleHistoryAdd = useCallback(() => {
    const trimmed = historyInput.trim();
    if (!trimmed) return;
    setHistory((prev) => [...prev, trimmed]);
    setHistoryInput("");
  }, [historyInput]);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#05060a",
        color: "#e0e0e0",
        padding: "2rem",
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      <header style={{ marginBottom: "1.5rem" }}>
        <p style={{ fontSize: "0.9rem", color: "#888" }}>Person 2 — frontend experience</p>
        <h1 style={{ margin: 0 }}>Session UI + live sketch overlay</h1>
        <p style={{ maxWidth: 640, lineHeight: 1.6 }}>
          `SessionPage` wires up `useLiveSession`, renders the webcam feed, sends routine history, and keeps the
          live drawing sketch aligned with the user’s motion.
        </p>
      </header>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)",
          gap: "1.5rem",
          alignItems: "start",
        }}
      >
        <div>
          <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <input
            value={sessionId}
            onChange={(event) => setSessionId(event.target.value)}
            placeholder="Session ID"
            style={{
              padding: "0.5rem",
              borderRadius: 8,
              border: "1px solid rgba(255,255,255,0.2)",
              background: "#111",
              color: "#fff",
              minWidth: 160,
              fontSize: "0.9rem",
            }}
          />
            <input
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              placeholder="User ID"
              style={{
                padding: "0.5rem",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,0.2)",
                background: "#111",
                color: "#fff",
                minWidth: 160,
                fontSize: "0.9rem",
              }}
            />
            <input
              value={wsUrl}
              onChange={(event) => setWsUrl(event.target.value)}
              placeholder="WebSocket base URL"
              style={{
                flex: 1,
                padding: "0.5rem",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,0.2)",
                background: "#111",
                color: "#fff",
                fontSize: "0.9rem",
              }}
            />
          </div>
          <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <input
              value={sessionGoal}
              onChange={(event) => setSessionGoal(event.target.value)}
              placeholder="Session goal"
              style={{
                padding: "0.5rem",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,0.2)",
                background: "#111",
                color: "#fff",
                minWidth: 200,
                fontSize: "0.9rem",
              }}
            />
          </div>
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem" }}>
            <button
              type="button"
              onClick={handleStart}
              style={{
                padding: "0.65rem 1.2rem",
                borderRadius: 10,
                border: "none",
                background: "#1f93ff",
                color: "#fff",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Start session
            </button>
            <button
              type="button"
              onClick={() => {
                stop();
                setOverlayPoints([]);
              }}
              style={{
                padding: "0.65rem 1.2rem",
                borderRadius: 10,
                border: "1px solid rgba(255,255,255,0.25)",
                background: "transparent",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              End session
            </button>
            <span style={{ alignSelf: "center", opacity: 0.7 }}>{connectedLabel}</span>
          </div>

          <div
            ref={videoWrapperRef}
            onPointerMove={handlePointerMove}
            style={{ position: "relative", display: "inline-block" }}
          >
            <WebcamFeed ref={videoRef} />
            {showSketch && (
              <canvas
                ref={overlayRef}
                style={{
                  position: "absolute",
                  inset: 0,
                  pointerEvents: "none",
                }}
              />
            )}
            <div
              style={{
                position: "absolute",
                top: 8,
                left: 8,
                padding: "0.25rem 0.65rem",
                borderRadius: 999,
                background: "rgba(0,0,0,0.6)",
                fontSize: "0.75rem",
              }}
            >
              Sketch overlay {showSketch ? "on" : "off"}
            </div>
          </div>
          <div style={{ marginTop: "0.6rem", display: "grid", gap: "0.4rem" }}>
            <label
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.35rem",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={showSketch}
                onChange={() => setShowSketch((prev) => !prev)}
              />
              Show real-time sketch overlay
            </label>
            <span
              style={{
                fontSize: "0.85rem",
                color: correctionActive ? "#ff6b6b" : "#84ffcb",
              }}
            >
              {correctionActive
                ? "Model flagged a correction—highlighting overlay."
                : "No flagged corrections yet."}
            </span>
          </div>
        </div>

        <div style={{ position: "sticky", top: "1.5rem" }}>
          <TimerWidget mode={timerMode} durationMinutes={countdownMinutes} onModeChange={setTimerMode} />
          <div style={{ marginTop: "1rem" }}>
            <label style={{ fontSize: "0.85rem" }}>Countdown minutes</label>
            <input
              type="number"
              min={1}
              max={30}
              value={countdownMinutes}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (!Number.isNaN(next)) {
                  setCountdownMinutes(next);
                }
              }}
              style={{
                width: "100%",
                marginTop: "0.35rem",
                padding: "0.4rem",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,0.2)",
                background: "#111",
                color: "#fff",
              }}
            />
          </div>
        </div>
      </section>

      <section
        style={{
          marginTop: "2rem",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "1rem",
        }}
      >
        <div
          style={{
            padding: "1rem",
            borderRadius: 16,
            background: "#0c0e13",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <h2 style={{ margin: 0, fontSize: "1rem" }}>Real-time transcripts</h2>
          <div style={{ marginTop: "0.7rem", fontSize: "0.9rem", minHeight: 80 }}>
            {state.transcripts.slice(-6).map((line, index) => (
              <p key={`${line}-${index}`} style={{ margin: "0.25rem 0", lineHeight: 1.4 }}>
                {line}
              </p>
            ))}
          </div>
          <form onSubmit={handleSend} style={{ display: "flex", gap: "0.4rem", marginTop: "0.5rem" }}>
            <input
              value={inputMessage}
              onChange={(event) => setInputMessage(event.target.value)}
              placeholder="Send a cue to Gemini"
              style={{
                flex: 1,
                padding: "0.5rem",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,0.2)",
                background: "#111",
                color: "#fff",
              }}
            />
            <button
              type="submit"
              style={{
                padding: "0.55rem 0.9rem",
                borderRadius: 8,
                border: "none",
                background: "#fff",
                color: "#000",
                cursor: "pointer",
              }}
            >
              Send
            </button>
          </form>
          {state.errors.length > 0 && (
            <div style={{ marginTop: "0.75rem", color: "#ff7b7b" }}>
              {state.errors.map((err, idx) => (
                <p key={`${err}-${idx}`} style={{ margin: 0, fontSize: "0.85rem" }}>
                  {err}
                </p>
              ))}
            </div>
          )}
        </div>

        <div
          style={{
            padding: "1rem",
            borderRadius: 16,
            background: "#0c0e13",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <h2 style={{ margin: 0, fontSize: "1rem" }}>History & Next block hints</h2>
          <p style={{ marginTop: "0.4rem", fontSize: "0.85rem" }}>
            Track the exercise IDs that were already coached (used by routines module + backend). New entries help
            Person 3 deliver the next block faster.
          </p>
          <ul style={{ paddingLeft: "1rem", fontSize: "0.9rem", marginTop: "0.4rem", minHeight: 60 }}>
            {history.map((entry, index) => (
              <li key={`${entry}-${index}`}>{entry}</li>
            ))}
          </ul>
          <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.5rem" }}>
            <input
              value={historyInput}
              onChange={(event) => setHistoryInput(event.target.value)}
              placeholder="Add exercise id"
              style={{
                flex: 1,
                padding: "0.45rem",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,0.2)",
                background: "#111",
                color: "#fff",
              }}
            />
            <button
              type="button"
              onClick={handleHistoryAdd}
              style={{
                padding: "0.45rem 0.8rem",
                borderRadius: 8,
                border: "none",
                background: "#1f93ff",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              Add
            </button>
          </div>
          <p style={{ fontSize: "0.75rem", marginTop: "0.4rem", opacity: 0.7 }}>
            When Person 3 calls `recommend_next_block`, it will consider this history + live context (fatigue/form) to
            pick the next exercise.
          </p>
        </div>
      </section>
    </div>
  );
}
