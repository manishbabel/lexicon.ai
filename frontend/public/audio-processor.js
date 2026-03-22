/**
 * AudioWorklet processor — runs in a dedicated audio thread.
 *
 * Receives raw float32 mic samples from the browser,
 * converts to 16-bit PCM at 16kHz for Deepgram.
 */

class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Int16Array(4096);
    this._bufferPos = 0;
    // Downsample from browser sample rate to 16kHz
    this._ratio = sampleRate / 16000;
    this._sampleAccum = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) return true;

    const samples = input[0]; // mono channel

    for (let i = 0; i < samples.length; i++) {
      this._sampleAccum += 1;
      if (this._sampleAccum >= this._ratio) {
        this._sampleAccum -= this._ratio;

        // Float32 [-1, 1] → Int16 [-32768, 32767]
        const s = Math.max(-1, Math.min(1, samples[i]));
        this._buffer[this._bufferPos++] = s < 0 ? s * 0x8000 : s * 0x7fff;

        // Send in chunks of 2048 samples (~128ms at 16kHz)
        if (this._bufferPos >= 2048) {
          const chunk = this._buffer.slice(0, this._bufferPos);
          this.port.postMessage(chunk.buffer, [chunk.buffer]);
          this._buffer = new Int16Array(4096);
          this._bufferPos = 0;
        }
      }
    }

    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
