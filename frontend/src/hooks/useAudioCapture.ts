/**
 * React hook for browser mic capture + Deepgram streaming.
 *
 * Called by useMeeting internally. Starts/stops audio capture
 * and forwards transcript results via a callback.
 */

import { useState, useRef, useCallback } from "react";
import { startCapture, type TranscriptResult, type CaptureHandle } from "../lib/audio";

export interface UseAudioCaptureReturn {
  isListening: boolean;
  error: string | null;
  audioLevel: number;
  start: (apiKey: string, onTranscript: (result: TranscriptResult) => void) => Promise<void>;
  stop: () => void;
}

export function useAudioCapture(): UseAudioCaptureReturn {
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState(0);
  const handleRef = useRef<CaptureHandle | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);

  // Compute RMS audio level from AnalyserNode at ~15fps
  const startLevelMonitor = useCallback((analyser: AnalyserNode) => {
    const dataArray = new Uint8Array(analyser.fftSize);
    let lastUpdate = 0;
    const INTERVAL = 1000 / 15; // ~15fps

    function tick(now: number) {
      if (now - lastUpdate >= INTERVAL) {
        analyser.getByteTimeDomainData(dataArray);
        // Compute RMS (root mean square) normalized to 0-1
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          const sample = (dataArray[i] - 128) / 128;
          sum += sample * sample;
        }
        const rms = Math.sqrt(sum / dataArray.length);
        // Scale up for better visual response (raw RMS is typically very small)
        const scaled = Math.min(1, rms * 4);
        setAudioLevel(scaled);
        lastUpdate = now;
      }
      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const stopLevelMonitor = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (analyserRef.current) {
      analyserRef.current.disconnect();
      analyserRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  const start = useCallback(
    async (apiKey: string, onTranscript: (result: TranscriptResult) => void) => {
      if (handleRef.current) return; // already running

      setError(null);

      try {
        const handle = await startCapture(apiKey, onTranscript, (err) => {
          setError(err.message);
          setIsListening(false);
          stopLevelMonitor();
          handleRef.current = null;
        });

        // Set up AnalyserNode for audio level metering
        const analyser = handle.audioCtx.createAnalyser();
        analyser.fftSize = 256;
        handle.source.connect(analyser);
        analyserRef.current = analyser;
        startLevelMonitor(analyser);

        handleRef.current = handle;
        setIsListening(true);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Mic access denied";
        setError(msg);
      }
    },
    [startLevelMonitor, stopLevelMonitor],
  );

  const stop = useCallback(() => {
    stopLevelMonitor();
    if (handleRef.current) {
      handleRef.current.stop();
      handleRef.current = null;
    }
    setIsListening(false);
    setError(null);
  }, [stopLevelMonitor]);

  return { isListening, error, audioLevel, start, stop };
}
