/**
 * Browser audio capture + Deepgram streaming transcription.
 *
 * Captures mic via getUserMedia, converts to 16-bit PCM via AudioWorklet,
 * streams directly to Deepgram's WS, and calls back with transcript text.
 */

export interface TranscriptResult {
  text: string;
  isFinal: boolean;
  speechFinal: boolean;
  speaker: string | null;
  confidence: number;
}

export type OnTranscript = (result: TranscriptResult) => void;

export interface CaptureHandle {
  stop: () => void;
  audioCtx: AudioContext;
  source: MediaStreamAudioSourceNode;
}

const DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen";

export async function startCapture(
  deepgramApiKey: string,
  onTranscript: OnTranscript,
  onError?: (err: Error) => void,
): Promise<CaptureHandle> {
  // 1. Get mic permission
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      channelCount: 1,
    },
  });

  console.log("[Lexicon] Mic access granted");

  // 2. Set up AudioContext + Worklet
  const audioCtx = new AudioContext();
  await audioCtx.audioWorklet.addModule("/audio-processor.js");

  const source = audioCtx.createMediaStreamSource(stream);
  const workletNode = new AudioWorkletNode(audioCtx, "pcm-processor");

  // Connect: mic → worklet → silent destination (keeps worklet alive)
  const silentGain = audioCtx.createGain();
  silentGain.gain.value = 0;
  source.connect(workletNode);
  workletNode.connect(silentGain);
  silentGain.connect(audioCtx.destination);

  console.log("[Lexicon] AudioWorklet ready, sample rate:", audioCtx.sampleRate);

  // 3. Open Deepgram WS
  const params = new URLSearchParams({
    encoding: "linear16",
    sample_rate: "16000",
    channels: "1",
    punctuate: "true",
    diarize: "true",
    interim_results: "true",
    utterance_end_ms: "1000",
    speech_final: "true",
    model: "nova-3",
  });

  const dgWs = new WebSocket(
    `${DEEPGRAM_WS_URL}?${params}`,
    ["token", deepgramApiKey],
  );
  dgWs.binaryType = "arraybuffer";

  let alive = true;
  let audioChunkCount = 0;

  // 4. Wait for Deepgram to connect, THEN wire audio
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error("Deepgram connection timeout"));
    }, 10000);

    dgWs.onopen = () => {
      clearTimeout(timeout);
      console.log("[Lexicon] Deepgram connected, wiring audio...");

      // Now wire PCM from worklet → Deepgram
      workletNode.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
        if (dgWs.readyState === WebSocket.OPEN) {
          dgWs.send(event.data);
          audioChunkCount++;
          if (audioChunkCount % 50 === 1) {
            console.log(`[Lexicon] Audio chunks sent: ${audioChunkCount}`);
          }
        }
      };

      resolve();
    };

    dgWs.onerror = () => {
      clearTimeout(timeout);
      reject(new Error("Deepgram WebSocket connection failed"));
    };
  });

  // 5. Receive transcripts from Deepgram
  dgWs.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      if (data.type === "Results") {
        const alt = data.channel?.alternatives?.[0];
        if (!alt?.transcript) return;

        const text = alt.transcript.trim();
        if (!text) return;

        console.log("[Lexicon] Transcript:", text, data.is_final ? "(final)" : "(partial)");

        // Get speaker from first word's diarization
        let speaker: string | null = null;
        const words = alt.words;
        if (words?.length > 0 && words[0].speaker !== undefined) {
          speaker = `Speaker ${words[0].speaker}`;
        }

        onTranscript({
          text,
          isFinal: data.is_final ?? false,
          speechFinal: data.speech_final ?? false,
          speaker,
          confidence: alt.confidence ?? 0,
        });
      }
    } catch {
      // Ignore non-JSON messages
    }
  };

  dgWs.onerror = (event) => {
    console.error("[Lexicon] Deepgram WS error:", event);
    onError?.(new Error("Deepgram WebSocket error"));
  };

  dgWs.onclose = (event) => {
    console.log("[Lexicon] Deepgram WS closed:", event.code, event.reason);
    if (alive) {
      onError?.(new Error(`Deepgram closed: ${event.code} ${event.reason || ""}`));
    }
  };

  // 6. Return stop handle
  function stop() {
    alive = false;

    // Close Deepgram
    if (dgWs.readyState === WebSocket.OPEN) {
      dgWs.send(JSON.stringify({ type: "CloseStream" }));
      dgWs.close();
    }

    // Stop audio
    workletNode.disconnect();
    source.disconnect();
    silentGain.disconnect();
    stream.getTracks().forEach((t) => t.stop());
    audioCtx.close();
    console.log(`[Lexicon] Audio stopped. Total chunks sent: ${audioChunkCount}`);
  }

  return { stop, audioCtx, source };
}
