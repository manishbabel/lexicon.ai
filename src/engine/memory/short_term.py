"""Short-term memory — JSONL-backed, 7-day rolling window.

Persists recent memories across turns within a session.
Each agent has its own short-term file:
  ~/.lexicon/sessions/<agent_id>/short_term.jsonl

Auto-prunes entries older than the retention period.
Searchable via keyword matching (fast, no embedding needed).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.shared.constants import SESSIONS_DIR, SHORT_TERM_RETENTION_DAYS
from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.memory.short_term")


@dataclass
class ShortTermEntry:
    """A single short-term memory entry."""
    content: str
    summary: str = ""
    source: str = "conversation"  # "conversation", "eviction", "tool", "reflection"
    agent_id: str = ""
    tags: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def age_days(self) -> float:
        """Age in days since creation."""
        return (time.time() - self.timestamp) / 86400


class ShortTermMemory:
    """JSONL-backed short-term memory with rolling window.

    Usage:
        stm = ShortTermMemory(agent_id="software-engineer")
        stm.append(ShortTermEntry(content="User discussed RAG pipeline"))
        results = stm.search("RAG", max_results=5)
        stm.prune()  # remove entries older than 7 days
    """

    def __init__(
        self,
        agent_id: str,
        retention_days: int = SHORT_TERM_RETENTION_DAYS,
    ):
        self.agent_id = agent_id
        self.retention_days = retention_days
        self._path = SESSIONS_DIR / agent_id / "short_term.jsonl"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: ShortTermEntry) -> None:
        """Append a memory entry to the JSONL file."""
        entry.agent_id = self.agent_id
        line = json.dumps(asdict(entry), default=str)
        with open(self._path, "a") as f:
            f.write(line + "\n")

    def append_many(self, entries: list[ShortTermEntry]) -> None:
        """Append multiple entries at once (batch flush from working memory)."""
        if not entries:
            return
        with open(self._path, "a") as f:
            for entry in entries:
                entry.agent_id = self.agent_id
                f.write(json.dumps(asdict(entry), default=str) + "\n")
        logger.debug(f"Flushed {len(entries)} entries to short-term memory")

    def read_all(self) -> list[ShortTermEntry]:
        """Read all entries from the JSONL file."""
        if not self._path.exists():
            return []

        entries = []
        with open(self._path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(ShortTermEntry(**data))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Skipping corrupt short-term entry: {e}")
        return entries

    def search(
        self,
        query: str,
        max_results: int = 5,
        max_age_days: float | None = None,
    ) -> list[ShortTermEntry]:
        """Search short-term memory by keyword.

        Case-insensitive substring match on content and summary.
        Returns most recent matches first.
        """
        query_lower = query.lower()
        cutoff = max_age_days or self.retention_days
        cutoff_ts = time.time() - (cutoff * 86400)

        matches = []
        for entry in reversed(self.read_all()):
            if entry.timestamp < cutoff_ts:
                continue
            if (
                query_lower in entry.content.lower()
                or query_lower in entry.summary.lower()
            ):
                matches.append(entry)
                if len(matches) >= max_results:
                    break

        return matches

    def get_recent(self, n: int = 10) -> list[ShortTermEntry]:
        """Get the N most recent entries."""
        entries = self.read_all()
        return entries[-n:] if len(entries) > n else entries

    def prune(self) -> int:
        """Remove entries older than retention_days.

        Rewrites the JSONL file without expired entries.
        Returns number of entries pruned.
        """
        entries = self.read_all()
        cutoff_ts = time.time() - (self.retention_days * 86400)
        kept = [e for e in entries if e.timestamp >= cutoff_ts]
        pruned_count = len(entries) - len(kept)

        if pruned_count > 0:
            with open(self._path, "w") as f:
                for entry in kept:
                    f.write(json.dumps(asdict(entry), default=str) + "\n")
            logger.info(
                f"Pruned {pruned_count} expired entries from "
                f"short-term memory ({self.agent_id})"
            )

        return pruned_count

    def to_context_string(self, max_entries: int = 5) -> str:
        """Format recent entries as context for prompt injection."""
        recent = self.get_recent(max_entries)
        if not recent:
            return ""

        lines = ["## Recent Session Memory"]
        for entry in recent:
            age = entry.age_days()
            age_str = f"{age:.1f}d ago" if age > 1 else "today"
            lines.append(f"- [{age_str}] {entry.summary or entry.content[:200]}")
        return "\n".join(lines)

    @property
    def entry_count(self) -> int:
        if not self._path.exists():
            return 0
        with open(self._path, "r") as f:
            return sum(1 for line in f if line.strip())
