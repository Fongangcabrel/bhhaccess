import { t } from "../../i18n";
import { useEffect, useRef, useState } from "react";
import { getQrDecoder, type QrDecoder } from "./decoder";

interface Props {
  /** Paused while a verdict is displayed or a request is in flight. */
  active: boolean;
  onDetect: (token: string) => void;
}

const CROP_RATIO = 0.8; // analyse the centre square (the viewfinder), not the whole picture
const CROP_MAX_SIDE = 720; // enough pixels for a 4 cm badge, cheap to decode
const MIN_INTERVAL_MS = 90; // ~11 analyses per second, never two at the same time

export function QrScanner({ active, onDetect }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const onDetectRef = useRef(onDetect);
  const activeRef = useRef(active);
  const [error, setError] = useState<string | null>(null);

  onDetectRef.current = onDetect;
  activeRef.current = active;

  useEffect(() => {
    let stream: MediaStream | null = null;
    let timer = 0;
    let stopped = false;
    let decoder: QrDecoder | null = null;

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError(t("camera.https"));
        return;
      }
      const decoderReady = getQrDecoder(); // loads while the camera starts
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: false,
        });
      } catch {
        setError(t("camera.denied"));
        return;
      }
      const video = videoRef.current;
      if (!video || stopped) return;
      video.srcObject = stream;
      await video.play().catch(() => undefined);
      void enableContinuousFocus(stream);
      try {
        decoder = await decoderReady;
      } catch {
        setError(t("camera.reader"));
        return;
      }
      loop();
    }

    function loop() {
      if (stopped) return;
      const startedAt = performance.now();
      void analyse().finally(() => {
        const wait = Math.max(0, MIN_INTERVAL_MS - (performance.now() - startedAt));
        if (!stopped) timer = window.setTimeout(loop, wait);
      });
    }

    async function analyse() {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!decoder || !activeRef.current || !video || !canvas || video.readyState < 2 || !video.videoWidth) return;
      const side = Math.floor(Math.min(video.videoWidth, video.videoHeight) * CROP_RATIO);
      const size = Math.min(side, CROP_MAX_SIDE);
      canvas.width = size;
      canvas.height = size;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) return;
      const sx = (video.videoWidth - side) / 2;
      const sy = (video.videoHeight - side) / 2;
      context.drawImage(video, sx, sy, side, side, 0, 0, size, size);
      try {
        const text = await decoder.decode(canvas);
        if (text && activeRef.current && !stopped) onDetectRef.current(text.trim());
      } catch {
        /* one unreadable frame: try the next one */
      }
    }

    void start();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  if (error) return <p role="alert" className="error center">{error}</p>;
  return (
    <div className="viewfinder">
      <video ref={videoRef} playsInline muted />
      <canvas ref={canvasRef} hidden />
      <div className="frame" aria-hidden />
    </div>
  );
}

/** Ask for continuous autofocus where the camera supports it (Android); ignored elsewhere. */
async function enableContinuousFocus(stream: MediaStream) {
  const track = stream.getVideoTracks()[0];
  const capabilities = (track?.getCapabilities?.() ?? {}) as { focusMode?: string[] };
  if (!capabilities.focusMode?.includes("continuous")) return;
  try {
    await track.applyConstraints({ advanced: [{ focusMode: "continuous" } as MediaTrackConstraintSet] });
  } catch {
    /* not critical */
  }
}
