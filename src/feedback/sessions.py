"""Session tracking CRUD — track meeting sessions and their stats."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from src.shared.logger import get_logger

from .db import get_connection

logger = get_logger("lexicon.feedback.sessions")


def _now() -> str:
    return datetime.utcnow().isoformat()


def create_session(
    persona: str = "software-engineer",
    metadata: dict[str, Any] | None = None,
) -> str:
    """Create a new meeting session. Returns the session ID."""
    session_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (id, persona, metadata) VALUES (?, ?, ?)",
        (session_id, persona, json.dumps(metadata or {})),
    )
    conn.commit()
    logger.info(f"Created session: {session_id} ({persona})")
    return session_id


def end_session(session_id: str) -> None:
    """Mark a session as ended."""
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET status = 'ended', ended_at = ? WHERE id = ?",
        (_now(), session_id),
    )
    conn.commit()


def pause_session(session_id: str) -> None:
    """Mark a session as paused."""
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET status = 'paused' WHERE id = ?",
        (session_id,),
    )
    conn.commit()


def resume_session(session_id: str) -> None:
    """Resume a paused session."""
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET status = 'active' WHERE id = ?",
        (session_id,),
    )
    conn.commit()


def bump_session_suggested(session_id: str) -> None:
    """Increment terms_suggested counter for a session."""
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET terms_suggested = terms_suggested + 1 WHERE id = ?",
        (session_id,),
    )
    conn.commit()


def bump_session_used(session_id: str) -> None:
    """Increment terms_used counter for a session."""
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET terms_used = terms_used + 1 WHERE id = ?",
        (session_id,),
    )
    conn.commit()


def bump_session_dismissed(session_id: str) -> None:
    """Increment terms_dismissed counter for a session."""
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET terms_dismissed = terms_dismissed + 1 WHERE id = ?",
        (session_id,),
    )
    conn.commit()


def get_session(session_id: str) -> dict[str, Any] | None:
    """Get a session by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["metadata"] = json.loads(result.get("metadata", "{}"))
    return result


def get_active_sessions() -> list[dict[str, Any]]:
    """Get all active sessions."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE status = 'active' ORDER BY started_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_sessions(limit: int = 10) -> list[dict[str, Any]]:
    """Get recent sessions (any status)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
