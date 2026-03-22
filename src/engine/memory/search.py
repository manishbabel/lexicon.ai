"""MemorySearcher — enhanced unified search with MMR and temporal decay.

Upgrades the basic score-sort in MemoryManager.recall() with:
  1. Temporal decay: recent results score higher than stale ones
  2. MMR (Maximal Marginal Relevance): iteratively selects results that
     are both relevant AND diverse, avoiding near-duplicate context.

Text similarity uses Jaccard distance on word sets (no embeddings needed).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.search.qmd_client import QMDClient
from src.shared.logger import get_logger

if TYPE_CHECKING:
    from .manager import RecallResult

logger = get_logger("lexicon.engine.memory.search")


def temporal_decay(score: float, age_days: float, rate: float = 0.1) -> float:
    """Apply exponential temporal decay to a relevance score.

    Args:
        score: Original relevance score.
        age_days: Age of the result in days (>=0).
        rate: Decay rate. Higher = faster decay. 0.1 means ~37% at 10 days.

    Returns:
        Decayed score.
    """
    if age_days < 0:
        age_days = 0.0
    return score * math.exp(-rate * age_days)


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity on word sets (case-insensitive).

    Returns a value in [0, 1] where 1 means identical word sets.
    """
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


class MemorySearcher:
    """Re-ranks recall results using temporal decay and MMR diversity.

    Usage:
        searcher = MemorySearcher()
        reranked = await searcher.search(query, raw_results)
    """

    def __init__(self, qmd: QMDClient | None = None):
        self.qmd = qmd

    async def search(
        self,
        query: str,
        sources: list[RecallResult],
        mmr_lambda: float = 0.7,
        decay_rate: float = 0.1,
    ) -> list[RecallResult]:
        """Re-rank results with temporal decay and MMR diversity.

        Args:
            query: The original search query.
            sources: Raw RecallResult list from all memory layers.
            mmr_lambda: Balance between relevance (1.0) and diversity (0.0).
                        Default 0.7 favors relevance.
            decay_rate: Exponential decay rate for temporal weighting.

        Returns:
            Re-ranked list of RecallResult (scores updated in-place).
        """
        if not sources:
            return []

        # Step 1: Apply temporal decay to scores
        now = datetime.now(tz=timezone.utc)
        for result in sources:
            ts = result.metadata.get("timestamp")
            if ts is not None:
                try:
                    if isinstance(ts, str):
                        result_time = datetime.fromisoformat(ts)
                    elif isinstance(ts, (int, float)):
                        result_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                    else:
                        continue
                    # Ensure timezone-aware comparison
                    if result_time.tzinfo is None:
                        result_time = result_time.replace(tzinfo=timezone.utc)
                    age_days = (now - result_time).total_seconds() / 86400.0
                    result.score = temporal_decay(result.score, age_days, decay_rate)
                except (ValueError, TypeError, OSError):
                    pass  # leave score unchanged if timestamp is unparseable

        # Step 2: MMR re-ranking
        return self._mmr_rerank(sources, mmr_lambda)

    def _mmr_rerank(
        self,
        candidates: list[RecallResult],
        mmr_lambda: float,
    ) -> list[RecallResult]:
        """Maximal Marginal Relevance re-ranking.

        Iteratively selects the candidate that maximises:
            MMR_score = lambda * relevance - (1 - lambda) * max_sim_to_selected

        This balances relevance with diversity — near-duplicate results
        get penalised by their similarity to already-selected items.
        """
        if not candidates:
            return []

        selected: list[RecallResult] = []
        remaining = list(candidates)

        # First pick: highest relevance score (no diversity penalty yet)
        remaining.sort(key=lambda r: r.score, reverse=True)
        selected.append(remaining.pop(0))

        while remaining:
            best_idx = -1
            best_mmr = -float("inf")

            for i, candidate in enumerate(remaining):
                relevance = candidate.score

                # Max similarity to any already-selected result
                max_sim = 0.0
                for sel in selected:
                    sim = _jaccard_similarity(candidate.content, sel.content)
                    if sim > max_sim:
                        max_sim = sim

                mmr_score = mmr_lambda * relevance - (1 - mmr_lambda) * max_sim

                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected
