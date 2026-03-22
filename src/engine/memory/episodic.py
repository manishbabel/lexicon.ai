"""Episodic memory — per-meeting JSONL records.

Each meeting gets its own JSONL file:
  ~/.lexicon/sessions/<agent_id>/episodic/<meeting_id>.jsonl

Records transcript chunks, suggestions made, tools called, and
decisions captured during the meeting. Used for cross-meeting search
("what did we discuss about RAG last week?") and post-meeting digests.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.shared.constants import SESSIONS_DIR
from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.memory.episodic")


@dataclass
class EpisodicEntry:
    """A single event in a meeting's episodic record."""
    type: str  # "transcript", "suggestion", "tool_call", "decision", "note"
    content: str
    agent_id: str = ""
    meeting_id: str = ""
    speaker: str = ""  # who said it (if known)
    tags: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class EpisodicMemory:
    """Per-meeting JSONL episodic memory.

    Usage:
        em = EpisodicMemory(agent_id="software-engineer")
        em.append("mtg-123", EpisodicEntry(
            type="transcript",
            content="We should implement a RAG pipeline",
        ))

        # Search across all meetings
        results = em.search("RAG", max_results=5)

        # Get all entries for a specific meeting
        entries = em.get_meeting("mtg-123")

        # List all meetings
        meetings = em.list_meetings()
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._base_dir = SESSIONS_DIR / agent_id / "episodic"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _meeting_path(self, meeting_id: str) -> Path:
        return self._base_dir / f"{meeting_id}.jsonl"

    def append(self, meeting_id: str, entry: EpisodicEntry) -> None:
        """Append an entry to a meeting's episodic record."""
        entry.agent_id = self.agent_id
        entry.meeting_id = meeting_id

        path = self._meeting_path(meeting_id)
        line = json.dumps(asdict(entry), default=str)
        with open(path, "a") as f:
            f.write(line + "\n")

    def get_meeting(self, meeting_id: str) -> list[EpisodicEntry]:
        """Read all entries for a specific meeting."""
        path = self._meeting_path(meeting_id)
        if not path.exists():
            return []

        entries = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(EpisodicEntry(**data))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Skipping corrupt episodic entry: {e}")
        return entries

    def list_meetings(self) -> list[dict[str, Any]]:
        """List all meeting files with metadata.

        Returns list of {meeting_id, path, entry_count, first_ts, last_ts}.
        """
        meetings = []
        for path in sorted(self._base_dir.glob("*.jsonl")):
            meeting_id = path.stem
            entries = self.get_meeting(meeting_id)
            if entries:
                meetings.append({
                    "meeting_id": meeting_id,
                    "path": str(path),
                    "entry_count": len(entries),
                    "first_ts": entries[0].timestamp,
                    "last_ts": entries[-1].timestamp,
                })
        return meetings

    def search(
        self,
        query: str,
        max_results: int = 5,
        meeting_id: str | None = None,
        max_age_days: float | None = None,
    ) -> list[EpisodicEntry]:
        """Search episodic memory across meetings by keyword.

        Case-insensitive substring match on content.
        If meeting_id is given, searches only that meeting.
        Returns most recent matches first.
        """
        query_lower = query.lower()
        cutoff_ts = (time.time() - (max_age_days * 86400)) if max_age_days else 0

        if meeting_id:
            files = [self._meeting_path(meeting_id)]
        else:
            # Search all meetings, most recent first
            files = sorted(self._base_dir.glob("*.jsonl"), reverse=True)

        matches = []
        for path in files:
            if not path.exists():
                continue
            entries = self.get_meeting(path.stem)
            for entry in reversed(entries):
                if entry.timestamp < cutoff_ts:
                    continue
                if query_lower in entry.content.lower():
                    matches.append(entry)
                    if len(matches) >= max_results:
                        return matches

        return matches

    def get_meeting_summary(self, meeting_id: str) -> str:
        """Get a compact summary of a meeting for context injection."""
        entries = self.get_meeting(meeting_id)
        if not entries:
            return ""

        transcript_chunks = [
            e.content for e in entries if e.type == "transcript"
        ]
        suggestions = [
            e.content for e in entries if e.type == "suggestion"
        ]
        decisions = [
            e.content for e in entries if e.type == "decision"
        ]

        parts = [f"## Meeting: {meeting_id}"]
        if transcript_chunks:
            # Just show last few transcript chunks
            recent = transcript_chunks[-5:]
            parts.append("### Recent Discussion")
            parts.extend(f"- {chunk[:200]}" for chunk in recent)
        if suggestions:
            parts.append("### Suggestions Made")
            parts.extend(f"- {s[:150]}" for s in suggestions[-3:])
        if decisions:
            parts.append("### Decisions")
            parts.extend(f"- {d[:150]}" for d in decisions)

        return "\n".join(parts)

    def to_context_string(
        self,
        meeting_id: str | None = None,
        max_entries: int = 5,
    ) -> str:
        """Format episodic memory as context for prompt injection."""
        if meeting_id:
            return self.get_meeting_summary(meeting_id)

        # Summarize recent meetings
        meetings = self.list_meetings()
        if not meetings:
            return ""

        lines = ["## Past Meetings"]
        for m in meetings[-3:]:  # last 3 meetings
            entry_count = m["entry_count"]
            lines.append(f"- {m['meeting_id']}: {entry_count} entries")

        return "\n".join(lines)
