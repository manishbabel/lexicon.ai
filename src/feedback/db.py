"""SQLite sidecar — connection management and schema for term feedback + sessions.

Stores structured data that QMD can't handle: counters, timestamps, session state.
Database lives at ~/.lexicon/feedback.sqlite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.shared.constants import LEXICON_HOME
from src.shared.logger import get_logger

logger = get_logger("lexicon.feedback.db")

DB_PATH = LEXICON_HOME / "feedback.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS term_feedback (
    term_slug       TEXT PRIMARY KEY,
    times_suggested INTEGER NOT NULL DEFAULT 0,
    times_used      INTEGER NOT NULL DEFAULT 0,
    times_dismissed INTEGER NOT NULL DEFAULT 0,
    last_suggested_at TEXT,
    last_used_at      TEXT,
    last_dismissed_at TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    persona         TEXT NOT NULL DEFAULT 'software-engineer',
    status          TEXT NOT NULL DEFAULT 'active',
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at        TEXT,
    terms_suggested INTEGER NOT NULL DEFAULT 0,
    terms_used      INTEGER NOT NULL DEFAULT 0,
    terms_dismissed INTEGER NOT NULL DEFAULT 0,
    metadata        TEXT DEFAULT '{}'
);
"""

# Module-level connection (reused across calls)
_conn: sqlite3.Connection | None = None


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get or create a SQLite connection with schema initialized.

    Returns a connection with row_factory set to sqlite3.Row for dict-like access.
    """
    global _conn
    if _conn is not None:
        return _conn

    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    _conn = sqlite3.connect(str(path))
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")

    # Initialize schema
    _conn.executescript(SCHEMA)
    _conn.commit()

    logger.info(f"SQLite connection established: {path}")
    return _conn


def close_connection() -> None:
    """Close the module-level connection."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
        logger.info("SQLite connection closed")
