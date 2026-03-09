import { useEffect, useMemo, useState } from "react";

type TimerMode = "countdown" | "unknown";

type TimerWidgetProps = {
  mode: TimerMode;
  durationMinutes: number;
  onModeChange: (mode: TimerMode) => void;
};

export default function TimerWidget({ mode, durationMinutes, onModeChange }: TimerWidgetProps) {
  const [timeLeft, setTimeLeft] = useState(durationMinutes * 60);

  useEffect(() => {
    setTimeLeft(durationMinutes * 60);
  }, [durationMinutes]);

  useEffect(() => {
    if (mode !== "countdown") return undefined;
    const interval = window.setInterval(() => {
      setTimeLeft((prev) => Math.max(prev - 1, 0));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [mode]);

  const formattedTime = useMemo(() => {
    const minutes = Math.floor(timeLeft / 60)
      .toString()
      .padStart(2, "0");
    const seconds = (timeLeft % 60).toString().padStart(2, "0");
    return `${minutes}:${seconds}`;
  }, [timeLeft]);

  return (
    <div
      style={{
        border: "1px solid rgba(255,255,255,0.2)",
        borderRadius: 12,
        padding: "0.75rem 1rem",
        background: "rgba(16,16,16,0.6)",
        color: "#fff",
        fontFamily: "system-ui, sans-serif",
        width: 210,
      }}
    >
      <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>Timer mode</div>
      <div style={{ fontSize: "1.75rem", fontWeight: 600, margin: "0.35rem 0" }}>
        {mode === "countdown" ? formattedTime : "Unknown"}
      </div>
      <button
        type="button"
        onClick={() => onModeChange(mode === "countdown" ? "unknown" : "countdown")}
        style={{
          width: "100%",
          padding: "0.45rem",
          borderRadius: 8,
          border: "none",
          background: "rgba(255,255,255,0.12)",
          color: "#fff",
          cursor: "pointer",
        }}
      >
        Switch to {mode === "countdown" ? "unknown" : "countdown"} time
      </button>
    </div>
  );
}
