"""Deepgram STT provider — streaming WebSocket + REST batch transcription."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import httpx
import websockets

from src.shared.config import get_settings

from .transcription import STTProvider, TranscriptChunk

logger = logging.getLogger(__name__)

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"
DEEPGRAM_REST_URL = "https://api.deepgram.com/v1/listen"


class DeepgramProvider(STTProvider):
    """Deepgram speech-to-text via WebSocket (streaming) and REST (batch)."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key or get_settings().deepgram_api_key
        if not self._api_key:
            raise ValueError("DEEPGRAM_API_KEY is required")
        self._ws: websockets.WebSocketClientProtocol | None = None

    # ── Streaming (live audio) ──────────────────────────────────

    async def stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        encoding: str = "linear16",
    ) -> AsyncIterator[TranscriptChunk]:
        """Open WS to Deepgram, send audio chunks, yield transcript chunks."""

        params = (
            f"?encoding={encoding}"
            f"&sample_rate={sample_rate}"
            f"&channels={channels}"
            f"&punctuate=true"
            f"&diarize=true"
            f"&interim_results=true"
            f"&utterance_end_ms=1000"
            f"&speech_final=true"
            f"&model=nova-3"
        )

        headers = {"Authorization": f"Token {self._api_key}"}

        async with websockets.connect(
            DEEPGRAM_WS_URL + params,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
        ) as ws:
            self._ws = ws

            # Send audio in background, yield transcripts in foreground
            send_task = asyncio.create_task(self._send_audio(ws, audio_chunks))

            try:
                async for msg in ws:
                    chunk = self._parse_message(msg)
                    if chunk is not None:
                        yield chunk
            finally:
                send_task.cancel()
                self._ws = None

    async def _send_audio(
        self,
        ws: websockets.WebSocketClientProtocol,
        audio_chunks: AsyncIterator[bytes],
    ) -> None:
        """Forward audio chunks to Deepgram WS."""
        try:
            async for chunk in audio_chunks:
                await ws.send(chunk)
            # Signal end of audio
            await ws.send(json.dumps({"type": "CloseStream"}))
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error sending audio to Deepgram")

    def _parse_message(self, raw: str | bytes) -> TranscriptChunk | None:
        """Parse a Deepgram WS message into a TranscriptChunk."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

        msg_type = data.get("type")

        if msg_type == "Results":
            channel = data.get("channel", {})
            alternatives = channel.get("alternatives", [])
            if not alternatives:
                return None

            alt = alternatives[0]
            text = alt.get("transcript", "").strip()
            if not text:
                return None

            # Speaker diarization
            words = alt.get("words", [])
            speaker = None
            if words:
                speaker_id = words[0].get("speaker")
                if speaker_id is not None:
                    speaker = f"Speaker {speaker_id}"

            return TranscriptChunk(
                text=text,
                speaker=speaker,
                is_final=data.get("is_final", False),
                confidence=alt.get("confidence", 0.0),
                start=data.get("start", 0.0),
                end=data.get("start", 0.0) + data.get("duration", 0.0),
                speech_final=data.get("speech_final", False),
            )

        if msg_type == "UtteranceEnd":
            # Deepgram detected silence — speaker likely done
            return TranscriptChunk(
                text="",
                is_final=True,
                speech_final=True,
            )

        return None

    # ── Batch (complete audio file) ─────────────────────────────

    async def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav") -> str:
        """Send complete audio to Deepgram REST API, return full text."""
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": mime_type,
        }
        params = {
            "punctuate": "true",
            "diarize": "true",
            "model": "nova-3",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                DEEPGRAM_REST_URL,
                headers=headers,
                params=params,
                content=audio,
            )
            resp.raise_for_status()
            data = resp.json()

        # Extract transcript from response
        channels = data.get("results", {}).get("channels", [])
        if not channels:
            return ""

        alternatives = channels[0].get("alternatives", [])
        if not alternatives:
            return ""

        return alternatives[0].get("transcript", "")

    # ── Cleanup ─────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the WebSocket if open."""
        if self._ws:
            await self._ws.close()
            self._ws = None
