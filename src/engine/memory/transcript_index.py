"""Transcript indexer — flush episodic transcript entries to vault .md files.

After a meeting ends, reads transcript chunks from the JSONL episodic store,
re-chunks them (~500 chars with overlap), and writes Obsidian-compatible .md
files to vault/transcripts/ so QMD auto-indexes them for future search.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter

from src.engine.memory.episodic import EpisodicEntry, EpisodicMemory
from src.shared.constants import VAULT_DIR
from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.memory.transcript_index")

CHUNK_TARGET = 500  # target characters per chunk
CHUNK_OVERLAP = 80  # overlap between consecutive chunks


class TranscriptIndexer:
    """Indexes meeting transcripts from episodic memory into the vault.

    Usage:
        indexer = TranscriptIndexer(agent_id="software-engineer")
        count = await indexer.index_meeting("mtg-123")
        print(f"Indexed {count} transcript chunks")
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.episodic = EpisodicMemory(agent_id)
        self._transcripts_dir = VAULT_DIR / "transcripts"

    async def index_meeting(self, meeting_id: str) -> int:
        """Read transcript entries for a meeting and write them as vault .md files.

        Returns the number of chunks written.
        """
        entries = self.episodic.get_meeting(meeting_id)
        transcript_entries = [e for e in entries if e.type == "transcript"]

        if not transcript_entries:
            logger.info(f"No transcript entries for meeting {meeting_id}")
            return 0

        chunks = self._chunk_transcript(transcript_entries)

        self._transcripts_dir.mkdir(parents=True, exist_ok=True)

        for i, chunk in enumerate(chunks):
            self._write_chunk(meeting_id, i, chunk)

        logger.info(
            f"Indexed {len(chunks)} transcript chunks for meeting {meeting_id}"
        )
        return len(chunks)

    def _chunk_transcript(self, entries: list[EpisodicEntry]) -> list[dict]:
        """Combine transcript entries into ~500-char chunks with overlap.

        Each chunk preserves speaker attribution and timestamp from the first
        entry that contributes to it.
        """
        # Flatten entries into a list of (speaker, text, timestamp) segments
        segments: list[dict[str, Any]] = []
        for entry in entries:
            speaker = entry.speaker or "Unknown"
            segments.append({
                "speaker": speaker,
                "text": entry.content,
                "timestamp": entry.timestamp,
            })

        if not segments:
            return []

        chunks: list[dict] = []
        current_text = ""
        current_speakers: set[str] = set()
        first_ts = segments[0]["timestamp"]

        for seg in segments:
            line = f"[{seg['speaker']}]: {seg['text']}"
            current_speakers.add(seg["speaker"])

            if not current_text:
                first_ts = seg["timestamp"]

            candidate = (current_text + "\n" + line).strip() if current_text else line

            if len(candidate) >= CHUNK_TARGET and current_text:
                # Flush current chunk
                chunks.append({
                    "text": current_text,
                    "speakers": sorted(current_speakers),
                    "timestamp": first_ts,
                })

                # Start next chunk with overlap from the tail of current_text
                overlap = current_text[-CHUNK_OVERLAP:] if len(current_text) > CHUNK_OVERLAP else current_text
                current_text = (overlap + "\n" + line).strip()
                current_speakers = {seg["speaker"]}
                first_ts = seg["timestamp"]
            else:
                current_text = candidate

        # Flush remaining text
        if current_text.strip():
            chunks.append({
                "text": current_text,
                "speakers": sorted(current_speakers),
                "timestamp": first_ts,
            })

        return chunks

    def _write_chunk(self, meeting_id: str, chunk_index: int, chunk: dict) -> Path:
        """Write a single transcript chunk as an Obsidian-compatible .md file."""
        filename = f"{meeting_id}_{chunk_index}.md"
        path = self._transcripts_dir / filename

        ts = chunk["timestamp"]
        try:
            iso_ts = datetime.fromtimestamp(ts).isoformat()
        except (OSError, ValueError):
            iso_ts = str(ts)

        metadata = {
            "meeting_id": meeting_id,
            "timestamp": iso_ts,
            "chunk_index": chunk_index,
            "speaker": ", ".join(chunk["speakers"]),
            "source": "transcript",
        }

        body = f"# Transcript — {meeting_id} (chunk {chunk_index})\n\n{chunk['text']}"

        post = frontmatter.Post(body, **metadata)
        content = frontmatter.dumps(post)
        path.write_text(content, encoding="utf-8")
        logger.info(f"Wrote transcript chunk: {path}")
        return path
