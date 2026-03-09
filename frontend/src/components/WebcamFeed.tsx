import { CSSProperties, ForwardedRef, forwardRef } from "react";

type WebcamFeedProps = {
  className?: string;
  style?: CSSProperties;
  onPointerMove?: (event: React.PointerEvent<HTMLDivElement>) => void;
};

const WebcamFeed = forwardRef(
  ({ className, style, onPointerMove }: WebcamFeedProps, ref: ForwardedRef<HTMLVideoElement>) => (
    <div
      onPointerMove={onPointerMove}
      style={{
        position: "relative",
        width: 640,
        height: 360,
        borderRadius: 16,
        overflow: "hidden",
        background: "#111",
        boxShadow: "0 15px 40px rgba(0,0,0,0.35)",
        ...style,
      }}
      className={className}
    >
      <video
        ref={ref}
        className="webcam-element"
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
        playsInline
        autoPlay
        muted
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "flex-end",
          padding: "0.5rem",
          pointerEvents: "none",
          fontSize: "0.75rem",
          color: "#fff",
          mixBlendMode: "difference",
        }}
      >
        Live preview
      </div>
    </div>
  )
);

export default WebcamFeed;
