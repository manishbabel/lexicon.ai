"""Built-in hook handlers — the actual side-effect functions.

These are registered during startup and fire automatically when events occur.
Each handler is a simple async function that does ONE thing.

Call register_builtin_hooks() during gateway startup to wire them all in.
"""

from __future__ import annotations

from typing import Any

from src.shared.logger import get_logger

from .registry import HookEvent, get_registry

logger = get_logger("lexicon.engine.hooks.builtin")


# ── Tool Hooks ────────────────────────────────────────────────────

async def reindex_qmd_after_vault_write(event: HookEvent) -> None:
    """After any vault write, trigger QMD to reindex.

    QMD picks up new/changed .md files and updates its search index.
    """
    from src.search.qmd_client import QMDClient

    path = event.data.get("path", "")
    logger.info(f"Reindexing QMD after vault write: {path}")

    client = QMDClient()
    if client.available:
        success = await client.update()
        if success:
            logger.debug("QMD reindex complete")
        else:
            logger.warning("QMD reindex failed")


async def check_duplicate_term_before_write(event: HookEvent) -> None:
    """Before writing a term to vault, check for duplicates.

    Logs a warning if a similar term already exists. Does not block the write.
    """
    path = event.data.get("path", "")
    if "/terms/" not in path:
        return

    from pathlib import Path
    term_path = Path(path)
    if term_path.exists():
        logger.warning(
            f"Term file already exists, will be overwritten: {path}"
        )


# ── Agent Hooks ───────────────────────────────────────────────────

async def flush_memory_on_agent_done(event: HookEvent) -> None:
    """After agent run completes, flush evicted working memory to short-term.

    The MemoryManager buffers evicted entries — this ensures they're persisted.
    """
    agent_id = event.data.get("agent_id", "")
    memory_manager = event.data.get("memory_manager")

    if memory_manager:
        flushed = memory_manager.flush()
        if flushed:
            logger.debug(f"Flushed {flushed} entries for agent '{agent_id}'")


async def log_agent_lifecycle(event: HookEvent) -> None:
    """Log all agent lifecycle events for observability."""
    agent_id = event.data.get("agent_id", "unknown")
    logger.info(f"Agent event: {event.name} | agent={agent_id}")


# ── Meeting Hooks ─────────────────────────────────────────────────

async def log_meeting_lifecycle(event: HookEvent) -> None:
    """Log meeting start/stop/pause events."""
    session_id = event.data.get("session_id", "unknown")
    logger.info(f"Meeting event: {event.name} | session={session_id}")


async def enqueue_meeting_digest(event: HookEvent) -> None:
    """After meeting stops, enqueue a meeting-digest agent run.

    The meeting-digest skill processes the transcript and extracts
    decisions, new terms, and topics into the vault.
    """
    session_id = event.data.get("session_id", "")
    queue = event.data.get("queue")
    if not queue:
        logger.debug("No queue in event data, skipping meeting digest enqueue")
        return

    logger.info(f"Enqueuing meeting-digest for session {session_id}")

    await queue.enqueue(
        session_key=f"session:{session_id}:software-engineer",
        content=(
            "[POST-MEETING DIGEST] The meeting just ended. "
            "Run the meeting-digest skill: summarize the meeting, "
            "extract new terms, decisions, and key topics. "
            "Write results to the vault."
        ),
        lane="main",
    )


# ── Command Hooks ─────────────────────────────────────────────────

async def log_command(event: HookEvent) -> None:
    """Log all user commands for observability."""
    args = event.data.get("args", "")
    logger.info(f"Command: {event.name} | args={args}")


# ── Gateway Hooks ─────────────────────────────────────────────────

async def log_gateway_lifecycle(event: HookEvent) -> None:
    """Log gateway startup/shutdown."""
    logger.info(f"Gateway event: {event.name}")


# ── Transcript Hooks ──────────────────────────────────────────────

async def store_transcript_in_episodic(event: HookEvent) -> None:
    """Store each transcript chunk in episodic memory for the meeting."""
    memory_manager = event.data.get("memory_manager")
    meeting_id = event.data.get("meeting_id", "")
    text = event.data.get("text", "")
    speaker = event.data.get("speaker", "")

    if memory_manager and meeting_id and text:
        memory_manager.store_episodic(
            meeting_id=meeting_id,
            entry_type="transcript",
            content=text,
            speaker=speaker,
        )


# ── Registration ──────────────────────────────────────────────────

def register_builtin_hooks() -> None:
    """Register all built-in hooks. Call once during gateway startup."""
    registry = get_registry()

    # Tool hooks
    registry.register("tool:after:vault_write", reindex_qmd_after_vault_write)
    registry.register("tool:before:vault_write", check_duplicate_term_before_write)

    # Agent hooks
    registry.register("agent:done", flush_memory_on_agent_done)
    registry.register("agent", log_agent_lifecycle)

    # Meeting hooks
    registry.register("meeting", log_meeting_lifecycle)
    registry.register("meeting:stop", enqueue_meeting_digest)

    # Command hooks
    registry.register("command", log_command)

    # Gateway hooks
    registry.register("gateway", log_gateway_lifecycle)

    # Transcript hooks
    registry.register("transcript:chunk", store_transcript_in_episodic)

    count = registry.handler_count()
    logger.info(f"Registered {count} built-in hooks")
