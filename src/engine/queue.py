"""Lane-based FIFO command queue (OpenClaw pattern).

Serializes agent runs per session while allowing controlled parallelism globally.

Key concepts:
- Session Lane: one per conversation, concurrency=1 (strict serial)
- Global Lanes: main (cap=4), subagent (cap=8), cron (parallel)
- Queue Modes: steer (inject mid-run), collect (merge for followup), followup (next turn)
- Debounce: wait before starting a run (coalesce rapid messages)
- Overflow: cap queued messages, summarize if exceeded
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.queue")


# ── Data Types ─────────────────────────────────────────────────────


class QueueMode(str, Enum):
    """How new messages interact with an active run."""

    STEER = "steer"
    """Inject immediately into current run at next tool boundary.
    Falls back to FOLLOWUP if no run is active."""

    COLLECT = "collect"
    """Coalesce all queued messages into a single followup turn (default)."""

    FOLLOWUP = "followup"
    """Enqueue for the next agent turn after current run completes."""


class RunPhase(str, Enum):
    """Lifecycle phases of an agent run."""

    QUEUED = "queued"
    START = "start"
    RUNNING = "running"
    END = "end"
    ERROR = "error"


@dataclass
class QueuedMessage:
    """A message waiting in the queue."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_key: str = ""
    content: str = ""
    mode: QueueMode = QueueMode.COLLECT
    metadata: dict[str, Any] = field(default_factory=dict)
    enqueued_at: float = field(default_factory=time.time)


@dataclass
class AgentRun:
    """An active or completed agent run."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_key: str = ""
    input_messages: list[QueuedMessage] = field(default_factory=list)
    phase: RunPhase = RunPhase.QUEUED
    started_at: float | None = None
    ended_at: float | None = None


@dataclass
class LaneConfig:
    """Configuration for a global queue lane."""

    name: str
    max_concurrent: int = 1


# ── Command Queue ──────────────────────────────────────────────────


class CommandQueue:
    """Lane-based FIFO command queue.

    Flow:
    1. Gateway router calls enqueue() with a message
    2. If active run + mode=STEER → inject via steer callback, done
    3. Otherwise → add to session queue → reset debounce timer
    4. After debounce silence → drain session queue → create AgentRun
    5. Acquire global lane semaphore (respect concurrency cap)
    6. Call run_handler(AgentRun) — the runner takes over
    7. On completion → check for more queued messages → repeat

    Usage:
        queue = CommandQueue(run_handler=runner.handle_run)
        await queue.start()
        await queue.enqueue("session:mtg-123:chief", "event sourcing", QueueMode.STEER)
    """

    def __init__(
        self,
        run_handler: Callable[[AgentRun], Coroutine[Any, Any, None]],
        debounce_ms: int = 1000,
        cap_per_session: int = 20,
        overflow_policy: str = "summarize",
    ):
        self._run_handler = run_handler
        self._debounce_ms = debounce_ms
        self._cap = cap_per_session
        self._overflow_policy = overflow_policy

        # Global lane configs + semaphores
        self._lanes: dict[str, LaneConfig] = {
            "main": LaneConfig(name="main", max_concurrent=4),
            "subagent": LaneConfig(name="subagent", max_concurrent=8),
            "cron": LaneConfig(name="cron", max_concurrent=4),
        }
        self._lane_semaphores: dict[str, asyncio.Semaphore] = {
            name: asyncio.Semaphore(cfg.max_concurrent)
            for name, cfg in self._lanes.items()
        }

        # Per-session state
        self._session_queues: dict[str, list[QueuedMessage]] = defaultdict(list)
        self._active_runs: dict[str, AgentRun] = {}  # session_key → active run
        self._session_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Debounce timers per session
        self._debounce_tasks: dict[str, asyncio.Task] = {}

        # Steer callbacks: session_key → function that injects text into running agent
        self._steer_callbacks: dict[str, Callable[[str], None]] = {}

        # Lifecycle listeners
        self._lifecycle_callbacks: list[Callable[[AgentRun], Coroutine[Any, Any, None]]] = []

        self._running = False

    # ── Public API ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Start accepting and draining messages."""
        self._running = True
        logger.info("CommandQueue started")

    async def stop(self) -> None:
        """Stop the queue and cancel pending debounce timers."""
        self._running = False
        for task in self._debounce_tasks.values():
            task.cancel()
        self._debounce_tasks.clear()
        logger.info("CommandQueue stopped")

    async def enqueue(
        self,
        session_key: str,
        content: str,
        mode: QueueMode = QueueMode.COLLECT,
        lane: str = "main",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Enqueue a message for processing. Returns the message ID.

        If mode=STEER and there's an active run, injects directly (doesn't queue).
        Otherwise adds to session queue and resets debounce timer.
        """
        msg = QueuedMessage(
            session_key=session_key,
            content=content,
            mode=mode,
            metadata=metadata or {},
        )

        # STEER: try to inject into active run
        if mode == QueueMode.STEER:
            active = self._active_runs.get(session_key)
            if active and active.phase == RunPhase.RUNNING:
                steer_cb = self._steer_callbacks.get(session_key)
                if steer_cb:
                    steer_cb(content)
                    logger.debug(f"Steered into active run [{session_key}]: {content[:50]}...")
                    return msg.id

        # Add to session queue (with overflow handling)
        session_queue = self._session_queues[session_key]
        if len(session_queue) >= self._cap:
            self._handle_overflow(session_key, session_queue, msg)
        else:
            session_queue.append(msg)

        logger.debug(
            f"Enqueued [{mode.value}] for {session_key} "
            f"(depth: {len(session_queue)}): {content[:50]}..."
        )

        # Reset debounce timer
        self._reset_debounce(session_key, lane)
        return msg.id

    def register_steer_callback(self, session_key: str, callback: Callable[[str], None]) -> None:
        """Register a function to inject text into an active run.

        Called by the runner when it starts an agent run.
        The callback should call agent.inject_transcript(text).
        """
        self._steer_callbacks[session_key] = callback

    def unregister_steer_callback(self, session_key: str) -> None:
        """Remove steering callback when run ends."""
        self._steer_callbacks.pop(session_key, None)

    def on_lifecycle(self, callback: Callable[[AgentRun], Coroutine[Any, Any, None]]) -> None:
        """Register a lifecycle event listener (run:start, run:end, run:error)."""
        self._lifecycle_callbacks.append(callback)

    def is_running(self, session_key: str) -> bool:
        """Check if an agent run is active for a session."""
        run = self._active_runs.get(session_key)
        return run is not None and run.phase == RunPhase.RUNNING

    def get_queue_depth(self, session_key: str) -> int:
        """Get number of queued messages for a session."""
        return len(self._session_queues.get(session_key, []))

    def get_active_runs(self) -> dict[str, AgentRun]:
        """Get all currently active runs."""
        return dict(self._active_runs)

    # ── Debounce ───────────────────────────────────────────────────

    def _reset_debounce(self, session_key: str, lane: str) -> None:
        """Reset the debounce timer. After silence → drain."""
        existing = self._debounce_tasks.get(session_key)
        if existing and not existing.done():
            existing.cancel()

        self._debounce_tasks[session_key] = asyncio.create_task(
            self._debounce_then_drain(session_key, lane)
        )

    async def _debounce_then_drain(self, session_key: str, lane: str) -> None:
        """Wait for debounce period of silence, then drain."""
        await asyncio.sleep(self._debounce_ms / 1000.0)
        await self._drain_session(session_key, lane)

    # ── Drain ──────────────────────────────────────────────────────

    async def _drain_session(self, session_key: str, lane: str) -> None:
        """Pull all queued messages for a session and start an agent run."""
        if not self._running:
            return

        async with self._session_locks[session_key]:
            # Don't start if a run is already active (session lane concurrency=1)
            active = self._active_runs.get(session_key)
            if active and active.phase == RunPhase.RUNNING:
                return

            # Grab all queued messages
            messages = self._session_queues.pop(session_key, [])
            if not messages:
                return

            # Create the agent run
            run = AgentRun(
                session_key=session_key,
                input_messages=messages,
                phase=RunPhase.QUEUED,
            )

            # Execute on the global lane (respects concurrency cap)
            semaphore = self._lane_semaphores.get(lane, self._lane_semaphores["main"])
            asyncio.create_task(self._execute_run(run, session_key, semaphore))

    # ── Execute ────────────────────────────────────────────────────

    async def _execute_run(
        self,
        run: AgentRun,
        session_key: str,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Execute an agent run within global lane concurrency limits.

        Acquires the global semaphore, runs the handler, emits lifecycle events,
        and checks for more queued messages after completion.
        """
        async with semaphore:
            # Mark as active
            self._active_runs[session_key] = run
            run.phase = RunPhase.START
            run.started_at = time.time()
            await self._emit_lifecycle(run)

            try:
                run.phase = RunPhase.RUNNING
                await self._run_handler(run)
                run.phase = RunPhase.END
            except Exception as e:
                run.phase = RunPhase.ERROR
                logger.error(f"Agent run failed [{session_key}]: {e}")
            finally:
                run.ended_at = time.time()
                await self._emit_lifecycle(run)

                # Cleanup
                self._active_runs.pop(session_key, None)
                self.unregister_steer_callback(session_key)

                # Check if more messages arrived during this run
                if self._session_queues.get(session_key):
                    logger.debug(f"More messages queued during run, draining [{session_key}]")
                    await self._drain_session(session_key, "main")

    # ── Overflow ───────────────────────────────────────────────────

    def _handle_overflow(
        self,
        session_key: str,
        queue: list[QueuedMessage],
        new_msg: QueuedMessage,
    ) -> None:
        """Handle queue overflow based on configured policy."""
        if self._overflow_policy == "drop_old":
            queue.pop(0)
            queue.append(new_msg)

        elif self._overflow_policy == "drop_new":
            pass  # discard the new message

        elif self._overflow_policy == "summarize":
            # Compress first half into a summary, keep second half + new
            half = len(queue) // 2
            old_texts = " | ".join(m.content for m in queue[:half])
            summary = QueuedMessage(
                session_key=session_key,
                content=f"[Summary of {half} earlier messages]: {old_texts[:500]}",
                mode=QueueMode.COLLECT,
                metadata={"summarized": True, "original_count": half},
            )
            queue[:half] = [summary]
            queue.append(new_msg)

        logger.warning(
            f"Queue overflow [{session_key}], policy={self._overflow_policy}, "
            f"depth={len(queue)}"
        )

    # ── Lifecycle Events ───────────────────────────────────────────

    async def _emit_lifecycle(self, run: AgentRun) -> None:
        """Notify all lifecycle listeners."""
        for cb in self._lifecycle_callbacks:
            try:
                await cb(run)
            except Exception as e:
                logger.error(f"Lifecycle callback error: {e}")
