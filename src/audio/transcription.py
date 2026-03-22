"""Abstract STT provider — all speech-to-text backends implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from pydantic import BaseModel, Field


class TranscriptChunk(BaseModel):
    """A single piece of transcribed speech."""

    text: str
    speaker: str | None = None
    is_final: bool = False
    confidence: float = 1.0
    start: float = 0.0  # seconds into audio
    end: float = 0.0

    # Deepgram sends partial updates that overwrite previous partials.
    # Only `is_final=True` chunks are committed to the transcript.
    speech_final: bool = Field(
        default=False,
        description="True when Deepgram detects end-of-utterance (speech_final). "
        "Useful for knowing when a speaker finished a sentence.",
    )


class STTProvider(ABC):
    """Contract for any speech-to-text provider (Deepgram, Whisper, etc.)."""

    @abstractmethod
    async def stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        encoding: str = "linear16",
    ) -> AsyncIterator[TranscriptChunk]:
        """Stream audio chunks, yield transcript chunks as they arrive.

        Used for live meetings — audio flows in, transcript flows out.
        """
        ...

    @abstractmethod
    async def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav") -> str:
        """Transcribe a complete audio buffer. Returns full text.

        Used for post-processing recorded audio files.
        """
        ...

    async def close(self) -> None:
        """Clean up connections. Override if provider holds state."""
