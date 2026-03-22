"""Transcript buffer — batches Deepgram's rapid-fire output into clean chunks."""

from __future__ import annotations

import asyncio
import time
import logging
from typing import Callable, Awaitable
from uuid import uuid4

from pydantic import BaseModel

from .transcription import TranscriptChunk

logger = logging.getLogger(__name__)

# Flush when either threshold is hit
FLUSH_INTERVAL_S = 2.0
FLUSH_WORD_COUNT = 5


class BufferedEntry(BaseModel):
    """A clean transcript entry ready for the gateway."""

    id: str
    speaker: str | None
    text: str
    timestamp: float
    is_final: bool


# Callback type: what happens when buffer flushes
FlushCallback = Callable[[BufferedEntry], Awaitable[None]]


class TranscriptBuffer:
    """Collects TranscriptChunks, flushes batched entries to a callback.

    - Holds partials, only forwards the latest partial text for UI updates
    - On `is_final`, commits text and starts batching
    - Flushes every FLUSH_INTERVAL_S or FLUSH_WORD_COUNT words
    - Groups consecutive chunks from the same speaker
    """

    def __init__(self, on_flush: FlushCallback) -> None:
        self._on_flush = on_flush
        self._current_speaker: str | None = None
        self._pending_text: list[str] = []
        self._pending_since: float = 0.0
        self._flush_timer: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def feed(self, chunk: TranscriptChunk) -> BufferedEntry | None:
        """Feed a chunk from Deepgram. Returns a partial entry for UI, or None.

        Final entries are batched and flushed via the callback.
        """
        if not chunk.text:
            # Empty chunk (e.g. UtteranceEnd) — force flush pending
            if chunk.speech_final:
                await self._flush()
            return None

        # Partial — return for live UI update, don't commit
        if not chunk.is_final:
            return BufferedEntry(
                id=f"partial-{uuid4().hex[:8]}",
                speaker=chunk.speaker or self._current_speaker,
                text=chunk.text,
                timestamp=time.time(),
                is_final=False,
            )

        # Final — commit to pending buffer
        async with self._lock:
            # Speaker changed — flush previous speaker's text first
            if chunk.speaker and chunk.speaker != self._current_speaker and self._pending_text:
                await self._do_flush()

            self._current_speaker = chunk.speaker or self._current_speaker

            if not self._pending_text:
                self._pending_since = time.time()
                self._start_timer()

            self._pending_text.append(chunk.text)

            # Check word count threshold
            total_words = sum(len(t.split()) for t in self._pending_text)
            if total_words >= FLUSH_WORD_COUNT:
                await self._do_flush()

        return None

    async def _flush(self) -> None:
        """Force flush any pending text."""
        async with self._lock:
            if self._pending_text:
                await self._do_flush()

    async def _do_flush(self) -> None:
        """Flush pending text — must be called under lock."""
        if not self._pending_text:
            return

        self._cancel_timer()

        entry = BufferedEntry(
            id=uuid4().hex[:12],
            speaker=self._current_speaker,
            text=" ".join(self._pending_text),
            timestamp=self._pending_since,
            is_final=True,
        )

        self._pending_text.clear()

        try:
            await self._on_flush(entry)
        except Exception:
            logger.exception("Error in flush callback")

    def _start_timer(self) -> None:
        """Start a timer to auto-flush after FLUSH_INTERVAL_S."""
        self._cancel_timer()
        self._flush_timer = asyncio.create_task(self._timer_flush())

    def _cancel_timer(self) -> None:
        if self._flush_timer and not self._flush_timer.done():
            self._flush_timer.cancel()
            self._flush_timer = None

    async def _timer_flush(self) -> None:
        """Auto-flush after timeout."""
        try:
            await asyncio.sleep(FLUSH_INTERVAL_S)
            await self._flush()
        except asyncio.CancelledError:
            pass

    async def close(self) -> None:
        """Flush remaining and clean up."""
        await self._flush()
        self._cancel_timer()
