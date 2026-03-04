import { useCallback, useEffect, useRef, useState } from "react";

type LiveEvent = {
  type: string;
  text?: string;
  data?: string;
  mime_type?: string;
  interrupt?: boolean;
  [k: string]: unknown;
};

type StartPayload = {
  sessionId: string;
  userId?: string;
  wsUrl: string;
  parentId?: string;
  timeRemainingSec?: number;
  sessionGoal?: string;
  videoElement: HTMLVideoElement;
};

type LiveSessionState = {
  connected: boolean;
  transcripts: string[];
  errors: string[];
};

const VIDEO_FPS = 1;
const AUDIO_SAMPLE_RATE = 16000;

export function useLiveSession() {
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRef = useRef<MediaStream | null>(null);
  const videoTickerRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  const [state, setState] = useState<LiveSessionState>({
    connected: false,
    transcripts: [],
    errors: [],
  });

  const appendTranscript = useCallback((line: string) => {
    setState((prev) => ({ ...prev, transcripts: [...prev.transcripts, line] }));
  }, []);

  const appendError = useCallback((line: string) => {
    setState((prev) => ({ ...prev, errors: [...prev.errors, line] }));
  }, []);

  const sendJson = useCallback((payload: object) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(payload));
  }, []);

  const playPcm16 = useCallback(async (base64Pcm: string, sampleRate = 24000) => {
    const context = audioContextRef.current ?? new AudioContext({ sampleRate });
    audioContextRef.current = context;

    const raw = base64ToBytes(base64Pcm);
    const pcm16 = new Int16Array(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength));
    const audio = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i += 1) {
      audio[i] = pcm16[i] / 32768;
    }

    const buffer = context.createBuffer(1, audio.length, sampleRate);
    buffer.copyToChannel(audio, 0);
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    source.start();
  }, []);

  const stop = useCallback(() => {
    sendJson({ type: "end" });

    if (videoTickerRef.current !== null) {
      window.clearInterval(videoTickerRef.current);
      videoTickerRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current.onaudioprocess = null;
      processorRef.current = null;
    }

    if (audioContextRef.current) {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (mediaRef.current) {
      mediaRef.current.getTracks().forEach((t) => t.stop());
      mediaRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setState((prev) => ({ ...prev, connected: false }));
  }, [sendJson]);

  const start = useCallback(
    async ({ sessionId, userId, wsUrl, parentId, timeRemainingSec, sessionGoal, videoElement }: StartPayload) => {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 360, frameRate: VIDEO_FPS },
        audio: true,
      });
      mediaRef.current = stream;

      videoElement.srcObject = stream;
      videoElement.muted = true;
      await videoElement.play();

      const resolvedUserId = userId ?? parentId ?? "parent";
      const ws = new WebSocket(
        `${wsUrl.replace(/\/$/, "")}/ws/${encodeURIComponent(resolvedUserId)}/${encodeURIComponent(sessionId)}`
      );
      wsRef.current = ws;

      ws.onopen = () => {
        setState((prev) => ({ ...prev, connected: true }));
        if (sessionGoal || timeRemainingSec) {
          ws.send(
            JSON.stringify({
              type: "text",
              text: `Session context: goal=${sessionGoal ?? "general coaching"}, time_remaining_sec=${timeRemainingSec ?? "unknown"}`,
            })
          );
        }
      };

      ws.onmessage = (evt) => {
        const event: LiveEvent = JSON.parse(evt.data);

        if (event.author === "user" && typeof event.content === "object") {
          const userText = extractTextFromAdkEvent(event);
          if (userText) appendTranscript(`You: ${userText}`);
        }

        if (event.author === "chaosfit_live_coach" && typeof event.content === "object") {
          const modelText = extractTextFromAdkEvent(event);
          if (modelText) appendTranscript(modelText);

          const adkAudio = extractAudioFromAdkEvent(event);
          if (adkAudio?.data) {
            void playPcm16(adkAudio.data, parseSampleRate(adkAudio.mimeType) ?? 24000);
          }
        }

        if (event.type === "model_text" && event.text) {
          appendTranscript(event.text);
        }
        if (event.type === "model_audio" && event.data) {
          void playPcm16(event.data, parseSampleRate(event.mime_type) ?? 24000);
        }
        if (event.type === "error") {
          appendError(String(event.message ?? "Live session error"));
        }
      };

      ws.onerror = () => {
        appendError("WebSocket error");
      };

      ws.onclose = () => {
        setState((prev) => ({ ...prev, connected: false }));
      };

      const canvas = document.createElement("canvas");
      canvas.width = 640;
      canvas.height = 360;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Failed to create canvas context");

      videoTickerRef.current = window.setInterval(() => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
        ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.65);
        const b64 = dataUrl.split(",")[1];
        sendJson({ type: "video", mime_type: "image/jpeg", data: b64 });
      }, Math.floor(1000 / VIDEO_FPS));

      const audioCtx = new AudioContext({ sampleRate: AUDIO_SAMPLE_RATE });
      audioContextRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const processor = audioCtx.createScriptProcessor(2048, 1, 1);
      processorRef.current = processor;
      source.connect(processor);
      processor.connect(audioCtx.destination);

      processor.onaudioprocess = (e: AudioProcessingEvent) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
        const input = e.inputBuffer.getChannelData(0);
        const pcm = floatTo16BitPCM(input);
        const b64 = bytesToBase64(new Uint8Array(pcm.buffer));
        sendJson({ type: "audio", mime_type: "audio/pcm;rate=16000", data: b64 });
      };
    },
    [appendError, appendTranscript, playPcm16, sendJson]
  );

  useEffect(() => stop, [stop]);

  return {
    state,
    start,
    stop,
    sendText: (text: string) => sendJson({ type: "text", text }),
  };
}

function floatTo16BitPCM(input: Float32Array): Int16Array {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i += 1) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return output;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function parseSampleRate(mimeType?: string): number | null {
  if (!mimeType) return null;
  const match = mimeType.match(/rate=(\d+)/);
  if (!match) return null;
  return Number(match[1]);
}

function extractTextFromAdkEvent(event: LiveEvent): string | null {
  const content = event.content as { parts?: Array<{ text?: string }> } | undefined;
  const parts = content?.parts ?? [];
  const out = parts
    .map((part) => (typeof part.text === "string" ? part.text : ""))
    .filter(Boolean)
    .join(" ");
  return out || null;
}

function extractAudioFromAdkEvent(event: LiveEvent): { data: string; mimeType?: string } | null {
  const content = event.content as {
    parts?: Array<{ inlineData?: { data?: string; mimeType?: string } }>;
  } | undefined;
  const parts = content?.parts ?? [];
  for (const part of parts) {
    if (part.inlineData?.data) {
      return { data: part.inlineData.data, mimeType: part.inlineData.mimeType };
    }
  }
  return null;
}
