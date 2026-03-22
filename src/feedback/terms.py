"""Term feedback CRUD — track how users interact with suggested terms.

Every time the system suggests a term, uses a term, or the user dismisses one,
we bump the counters here. The knowledge-consolidator and term-suggest skills
use this data to prioritize what to suggest next.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.shared.logger import get_logger

from .db import get_connection

logger = get_logger("lexicon.feedback.terms")


def _now() -> str:
    return datetime.utcnow().isoformat()


def _ensure_row(term_slug: str) -> None:
    """Create a row for this term if it doesn't exist."""
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO term_feedback (term_slug) VALUES (?)",
        (term_slug,),
    )
    conn.commit()


def bump_suggested(term_slug: str) -> None:
    """Increment times_suggested for a term."""
    _ensure_row(term_slug)
    conn = get_connection()
    conn.execute(
        "UPDATE term_feedback SET times_suggested = times_suggested + 1, last_suggested_at = ? WHERE term_slug = ?",
        (_now(), term_slug),
    )
    conn.commit()


def bump_used(term_slug: str) -> None:
    """Increment times_used — the user actually said this term."""
    _ensure_row(term_slug)
    conn = get_connection()
    conn.execute(
        "UPDATE term_feedback SET times_used = times_used + 1, last_used_at = ? WHERE term_slug = ?",
        (_now(), term_slug),
    )
    conn.commit()


def bump_dismissed(term_slug: str) -> None:
    """Increment times_dismissed — the user dismissed this suggestion."""
    _ensure_row(term_slug)
    conn = get_connection()
    conn.execute(
        "UPDATE term_feedback SET times_dismissed = times_dismissed + 1, last_dismissed_at = ? WHERE term_slug = ?",
        (_now(), term_slug),
    )
    conn.commit()


def get_feedback(term_slug: str) -> dict[str, Any] | None:
    """Get feedback stats for a specific term.

    Returns:
        {"term_slug": ..., "times_suggested": ..., "times_used": ..., ...} or None.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM term_feedback WHERE term_slug = ?",
        (term_slug,),
    ).fetchone()

    if row is None:
        return None
    return dict(row)


def get_all_feedback() -> list[dict[str, Any]]:
    """Get feedback stats for all terms."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM term_feedback ORDER BY times_suggested DESC").fetchall()
    return [dict(r) for r in rows]


def get_underused_terms(min_suggested: int = 3) -> list[dict[str, Any]]:
    """Get terms that are suggested often but rarely used.

    These are candidates for re-teaching or difficulty adjustment.

    Args:
        min_suggested: Minimum times_suggested to be considered (avoid noise from new terms).

    Returns:
        List of term feedback dicts, sorted by usage ratio (lowest first).
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *,
            CASE WHEN times_suggested > 0
                THEN CAST(times_used AS REAL) / times_suggested
                ELSE 0
            END AS usage_ratio
        FROM term_feedback
        WHERE times_suggested >= ?
        ORDER BY usage_ratio ASC
        """,
        (min_suggested,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_dismissed_terms(min_dismissed: int = 2) -> list[dict[str, Any]]:
    """Get terms the user frequently dismisses.

    These might be too basic or irrelevant — candidates for archival.

    Args:
        min_dismissed: Minimum dismissals to be included.

    Returns:
        List of term feedback dicts, sorted by dismissals (highest first).
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM term_feedback WHERE times_dismissed >= ? ORDER BY times_dismissed DESC",
        (min_dismissed,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_top_used_terms(limit: int = 20) -> list[dict[str, Any]]:
    """Get the most-used terms — the user's strongest vocabulary."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM term_feedback WHERE times_used > 0 ORDER BY times_used DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
