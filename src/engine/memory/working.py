"""Working memory — in-process deque for current turn context.

Fast, no disk I/O. Holds the most recent entries for the current
conversation. When capacity is exceeded, oldest entries are evicted
and optionally flushed to short-term memory.

This is what the agent "sees" right now — the active conversation
context that fits within the token budget.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.memory.working")

# Default capacity — tuned for ~50 interaction turns
DEFAULT_CAPACITY = 100


@dataclass
class WorkingMemoryEntry:
    """A single entry in working memory."""
    content: str
    role: str = "system"  # "user", "assistant", "system", "tool"
    source: str = "conversation"  # "conversation", "steering", "recall"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkingMemory:
    """Bounded in-process memory for the current agent turn.

    Usage:
        wm = WorkingMemory(capacity=100)
        wm.add("User asked about RAG", role="user")
        wm.add("Suggested RAG pipeline pattern", role="assistant")

        # Search by keyword
        results = wm.search("RAG")

        # Get recent context as a string (for prompt injection)
        context = wm.to_context_string(max_entries=10)

        # Evicted entries returned for flush to short-term
        evicted = wm.get_and_clear_evicted()
    """

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        self._capacity = capacity
        self._entries: deque[WorkingMemoryEntry] = deque(maxlen=capacity)
        self._evicted: list[WorkingMemoryEntry] = []

    def add(
        self,
        content: str,
        role: str = "system",
        source: str = "conversation",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add an entry. If at capacity, oldest is evicted."""
        if len(self._entries) >= self._capacity:
            evicted = self._entries[0]  # will be dropped by deque
            self._evicted.append(evicted)

        self._entries.append(WorkingMemoryEntry(
            content=content,
            role=role,
            source=source,
            metadata=metadata or {},
        ))

    def search(self, query: str, max_results: int = 5) -> list[WorkingMemoryEntry]:
        """Simple keyword search over working memory.

        Case-insensitive substring match. Returns most recent matches first.
        """
        query_lower = query.lower()
        matches = [
            entry for entry in reversed(self._entries)
            if query_lower in entry.content.lower()
        ]
        return matches[:max_results]

    def get_recent(self, n: int = 10) -> list[WorkingMemoryEntry]:
        """Get the N most recent entries."""
        entries = list(self._entries)
        return entries[-n:] if len(entries) > n else entries

    def to_context_string(self, max_entries: int = 10) -> str:
        """Format recent entries as a context string for prompt injection.

        Returns a compact summary of recent working memory.
        """
        recent = self.get_recent(max_entries)
        if not recent:
            return ""

        lines = []
        for entry in recent:
            prefix = f"[{entry.role}]" if entry.role != "system" else ""
            lines.append(f"{prefix} {entry.content}".strip())
        return "\n".join(lines)

    def get_and_clear_evicted(self) -> list[WorkingMemoryEntry]:
        """Return entries evicted since last call and clear the eviction buffer.

        The caller (MemoryManager) should flush these to short-term memory.
        """
        evicted = self._evicted
        self._evicted = []
        return evicted

    def clear(self) -> None:
        """Clear all entries and eviction buffer."""
        self._entries.clear()
        self._evicted.clear()

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def capacity(self) -> int:
        return self._capacity
