"""MemoryManager — unified search/store/recall across all memory layers.

The single interface that AgentRuntime calls. Searches across:
  1. Working memory (in-process deque) — current turn
  2. QMD vault search (hybrid: BM25 + vector + rerank) — knowledge base
  3. Short-term JSONL — recent session memories (7-day window)
  4. Episodic JSONL — past meeting records

Results are merged, deduped, and formatted as context for the
agent's system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.search.qmd_client import QMDClient
from src.shared.logger import get_logger

from .episodic import EpisodicEntry, EpisodicMemory
from .short_term import ShortTermEntry, ShortTermMemory
from .working import WorkingMemory, WorkingMemoryEntry

logger = get_logger("lexicon.engine.memory.manager")

# Maximum context string length (chars) injected into system prompt
MAX_CONTEXT_CHARS = 4000

# How many results to pull from each source
QMD_SEARCH_LIMIT = 5
SHORT_TERM_SEARCH_LIMIT = 3
EPISODIC_SEARCH_LIMIT = 3
WORKING_SEARCH_LIMIT = 3


@dataclass
class RecallResult:
    """A single result from memory recall, normalized across sources."""
    content: str
    source: str  # "working", "vault", "short_term", "episodic"
    score: float = 0.0  # relevance score (0-1), best-effort
    path: str = ""  # vault file path (if from QMD)
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    """Unified memory interface for agent runtimes.

    Usage:
        mm = MemoryManager(agent_id="software-engineer")

        # Before agent runs: recall relevant context
        context = await mm.recall("retrieval augmented generation")
        runtime.set_memory_context(context)

        # During agent run: store interactions
        mm.store_interaction(user_input, assistant_response)

        # After meeting: store episodic entry
        mm.store_episodic(meeting_id, "transcript", content)

        # Periodic: flush evicted working memory + prune short-term
        mm.flush()
        mm.prune()
    """

    def __init__(
        self,
        agent_id: str,
        qmd_client: QMDClient | None = None,
        meeting_id: str | None = None,
    ):
        self.agent_id = agent_id
        self.meeting_id = meeting_id

        # Memory layers
        self.working = WorkingMemory()
        self.short_term = ShortTermMemory(agent_id=agent_id)
        self.episodic = EpisodicMemory(agent_id=agent_id)
        self.qmd = qmd_client or QMDClient()
        # Lazy import to avoid circular dependency (search.py uses RecallResult)
        from .search import MemorySearcher
        self.searcher = MemorySearcher(qmd=self.qmd)

        logger.info(f"MemoryManager initialized for agent '{agent_id}'")

    # ── Recall (search across all layers) ─────────────────────────

    async def recall(
        self,
        query: str,
        include_working: bool = True,
        include_vault: bool = True,
        include_short_term: bool = True,
        include_episodic: bool = True,
    ) -> str:
        """Search all memory layers and return formatted context string.

        This is what gets injected into the agent's system prompt
        as memory context.

        Args:
            query: Search query (typically the user's input or transcript chunk)
            include_*: Toggle which layers to search

        Returns:
            Formatted context string for system prompt injection
        """
        results: list[RecallResult] = []

        # 1. Working memory — fast, in-process
        if include_working:
            wm_results = self.working.search(query, max_results=WORKING_SEARCH_LIMIT)
            for entry in wm_results:
                results.append(RecallResult(
                    content=entry.content,
                    source="working",
                    score=0.8,  # working memory is high-relevance by recency
                ))

        # 2. QMD vault search — hybrid (BM25 + vector + rerank)
        if include_vault and self.qmd.available:
            try:
                qmd_results = await self.qmd.query(
                    query, n=QMD_SEARCH_LIMIT, min_score=0.1,
                )
                for r in qmd_results:
                    results.append(RecallResult(
                        content=r.get("content", "")[:500],
                        source="vault",
                        score=r.get("score", 0.0),
                        path=r.get("path", ""),
                    ))
            except Exception as e:
                logger.warning(f"QMD search failed during recall: {e}")

        # 3. Short-term JSONL — recent session memories
        if include_short_term:
            st_results = self.short_term.search(
                query, max_results=SHORT_TERM_SEARCH_LIMIT,
            )
            for entry in st_results:
                # Score by recency: newer = higher
                age_penalty = min(entry.age_days() / 7.0, 1.0)
                results.append(RecallResult(
                    content=entry.summary or entry.content[:300],
                    source="short_term",
                    score=0.6 * (1.0 - age_penalty),
                ))

        # 4. Episodic — past meeting records
        if include_episodic:
            ep_results = self.episodic.search(
                query,
                max_results=EPISODIC_SEARCH_LIMIT,
                meeting_id=self.meeting_id,
            )
            for entry in ep_results:
                results.append(RecallResult(
                    content=entry.content[:300],
                    source="episodic",
                    score=0.5,
                    metadata={"meeting_id": entry.meeting_id, "type": entry.type},
                ))

        # Deduplicate, apply temporal decay, and MMR re-rank for diversity
        results = self._deduplicate(results)
        results = await self.searcher.search(query, results)

        # Format as context string
        context = self._format_context(results)
        logger.debug(
            f"Recalled {len(results)} results for '{query[:50]}...' "
            f"({len(context)} chars)"
        )
        return context

    # ── Store (write to memory layers) ────────────────────────────

    def store_interaction(self, user_input: str, assistant_response: str) -> None:
        """Store a user↔assistant interaction in working + short-term memory."""
        # Working memory
        self.working.add(user_input, role="user", source="conversation")
        if assistant_response:
            self.working.add(assistant_response, role="assistant", source="conversation")

        # Short-term — store a summary
        summary = self._summarize_interaction(user_input, assistant_response)
        self.short_term.append(ShortTermEntry(
            content=user_input,
            summary=summary,
            source="conversation",
        ))

    def store_episodic(
        self,
        meeting_id: str,
        entry_type: str,
        content: str,
        speaker: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store an episodic entry for the current meeting."""
        self.episodic.append(meeting_id, EpisodicEntry(
            type=entry_type,
            content=content,
            speaker=speaker,
            tags=tags or [],
            metadata=metadata or {},
        ))

    def store_note(self, content: str, tags: list[str] | None = None) -> None:
        """Store a note in working + short-term memory."""
        self.working.add(content, role="system", source="note")
        self.short_term.append(ShortTermEntry(
            content=content,
            summary=content[:200],
            source="note",
            tags=tags or [],
        ))

    # ── Flush & Prune ─────────────────────────────────────────────

    def flush(self) -> int:
        """Flush evicted working memory entries to short-term.

        Returns number of entries flushed.
        """
        evicted = self.working.get_and_clear_evicted()
        if not evicted:
            return 0

        st_entries = [
            ShortTermEntry(
                content=e.content,
                summary=e.content[:200],
                source="eviction",
                metadata=e.metadata,
            )
            for e in evicted
        ]
        self.short_term.append_many(st_entries)
        return len(st_entries)

    def prune(self) -> int:
        """Prune expired short-term entries. Returns count pruned."""
        return self.short_term.prune()

    # ── Context for Current Meeting ───────────────────────────────

    def get_meeting_context(self, meeting_id: str | None = None) -> str:
        """Get context for the current meeting (working + episodic).

        Used when the agent needs to know what's happened so far.
        """
        mid = meeting_id or self.meeting_id
        parts = []

        # Working memory context
        wm_ctx = self.working.to_context_string(max_entries=10)
        if wm_ctx:
            parts.append("## Current Conversation\n" + wm_ctx)

        # Episodic context for this meeting
        if mid:
            ep_ctx = self.episodic.to_context_string(meeting_id=mid)
            if ep_ctx:
                parts.append(ep_ctx)

        return "\n\n".join(parts) if parts else ""

    # ── Internal ──────────────────────────────────────────────────

    def _deduplicate(self, results: list[RecallResult]) -> list[RecallResult]:
        """Remove duplicate results by content similarity.

        Simple: exact match on first 100 chars of content.
        """
        seen: set[str] = set()
        deduped: list[RecallResult] = []
        for r in results:
            key = r.content[:100].strip().lower()
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped

    def _format_context(self, results: list[RecallResult]) -> str:
        """Format recall results as a context string for the system prompt."""
        if not results:
            return ""

        parts: list[str] = []
        total_chars = 0

        # Group by source for clarity
        by_source: dict[str, list[RecallResult]] = {}
        for r in results:
            by_source.setdefault(r.source, []).append(r)

        source_labels = {
            "working": "Current Context",
            "vault": "Knowledge Base",
            "short_term": "Recent Memory",
            "episodic": "Past Meetings",
        }

        for source in ["working", "vault", "short_term", "episodic"]:
            items = by_source.get(source, [])
            if not items:
                continue

            label = source_labels.get(source, source)
            section = [f"### {label}"]
            for r in items:
                entry_text = f"- {r.content}"
                if r.path:
                    entry_text += f" (source: {r.path})"

                if total_chars + len(entry_text) > MAX_CONTEXT_CHARS:
                    break
                section.append(entry_text)
                total_chars += len(entry_text)

            if len(section) > 1:  # has entries beyond header
                parts.append("\n".join(section))

        return "\n\n".join(parts)

    def _summarize_interaction(self, user_input: str, response: str) -> str:
        """Create a short summary of an interaction for short-term storage.

        Simple heuristic — first 150 chars of input + response.
        Could be enhanced with LLM summarization later.
        """
        input_short = user_input[:100].strip()
        response_short = response[:100].strip() if response else ""
        if response_short:
            return f"Q: {input_short} → A: {response_short}"
        return f"Q: {input_short}"

    # ── State ─────────────────────────────────────────────────────

    def set_meeting(self, meeting_id: str) -> None:
        """Set the current meeting ID (for episodic memory scoping)."""
        self.meeting_id = meeting_id

    def clear_working(self) -> None:
        """Clear working memory (e.g., on meeting end)."""
        self.flush()  # save evicted first
        self.working.clear()
