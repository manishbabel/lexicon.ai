"""Agent run executor — bridge between CommandQueue and AgentRuntime.

The queue decides WHEN to run. The runner decides HOW:
1. Resolve session_key → find the right agent in registry
2. Merge collected messages into one input
3. Wire steering so new chunks inject mid-run
4. Run AgentRuntime.run() → stream output to listeners
5. Persist transcript to session JSONL
6. Cleanup
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Coroutine

from src.shared.constants import SESSIONS_DIR
from src.shared.logger import get_logger
from src.shared.types import AgentOutput

from .queue import AgentRun, CommandQueue, QueuedMessage
from .registry import AgentRegistry
from .runtime import AgentRuntime

logger = get_logger("lexicon.engine.runner")


class AgentRunner:
    """Executes agent runs from the command queue.

    The gateway registers output listeners so agent output streams
    directly to the browser via WebSocket.

    Usage:
        runner = AgentRunner(registry, queue)
        # Gateway registers listener:
        runner.on_output("session:mtg-123:chief", send_to_websocket)
        # Queue calls runner.handle_run(agent_run) when draining
    """

    def __init__(self, registry: AgentRegistry, queue: CommandQueue):
        self.registry = registry
        self.queue = queue

        # Output listeners: session_key → [async callbacks]
        # Gateway registers these to stream output to WebSocket
        self._output_listeners: dict[
            str, list[Callable[[AgentOutput], Coroutine[Any, Any, None]]]
        ] = {}

    # ── Output Listeners ───────────────────────────────────────────

    def on_output(
        self,
        session_key: str,
        callback: Callable[[AgentOutput], Coroutine[Any, Any, None]],
    ) -> None:
        """Register an output listener. Gateway uses this to stream to WebSocket."""
        if session_key not in self._output_listeners:
            self._output_listeners[session_key] = []
        self._output_listeners[session_key].append(callback)

    def remove_output_listeners(self, session_key: str) -> None:
        """Remove all output listeners for a session."""
        self._output_listeners.pop(session_key, None)

    # ── Run Handler (called by queue) ──────────────────────────────

    async def handle_run(self, run: AgentRun) -> None:
        """Execute an agent run. This is the queue's run_handler.

        Steps:
        1. Resolve agent from session_key
        2. Merge collected messages
        3. Wire steering callback
        4. Run agent loop, stream output
        5. Persist transcript
        """
        session_key = run.session_key
        logger.info(
            f"Run {run.id} starting [{session_key}] "
            f"with {len(run.input_messages)} messages"
        )

        # 1. Resolve agent
        agent = self._resolve_agent(session_key)
        if not agent:
            logger.error(f"No agent found for session {session_key}")
            await self._emit_output(
                session_key,
                AgentOutput(type="error", error=f"No agent for session {session_key}"),
            )
            return

        # 2. Merge messages into single input
        input_text = self._merge_messages(run.input_messages)
        logger.debug(f"Merged input: {input_text[:100]}...")

        # 3. Wire steering callback
        self.queue.register_steer_callback(
            session_key,
            agent.inject_transcript,
        )

        # 4. Run agent loop and stream output
        full_response = ""
        tool_calls: list[dict[str, Any]] = []

        try:
            async for output in agent.run(input_text):
                # Stream to gateway → websocket → browser
                await self._emit_output(session_key, output)

                # Collect for transcript
                if output.type == "text_delta":
                    full_response += output.delta
                elif output.type == "tool_result":
                    tool_calls.append({
                        "tool": output.tool_name,
                        "input": output.tool_input,
                        "result": str(output.tool_result)[:500],
                        "timestamp": time.time(),
                    })

        except Exception as e:
            logger.error(f"Run {run.id} failed: {e}")
            await self._emit_output(
                session_key,
                AgentOutput(type="error", error=str(e)),
            )
            return

        # 5. Flush memory after run
        flushed = agent.flush_memory()
        if flushed:
            logger.debug(f"Flushed {flushed} memory entries for {session_key}")

        # 6. Persist transcript
        if full_response or tool_calls:
            self._persist_transcript(
                session_key=session_key,
                run_id=run.id,
                input_text=input_text,
                response=full_response,
                tool_calls=tool_calls,
            )

        logger.info(
            f"Run {run.id} complete: "
            f"{len(full_response)} chars, {len(tool_calls)} tool calls"
        )

    # ── Internal ───────────────────────────────────────────────────

    def _resolve_agent(self, session_key: str) -> AgentRuntime | None:
        """Extract agent_id from session_key and look up in registry.

        Session key formats:
          - "session:<session_id>:<agent_id>" — meeting session
          - "cron:<persona>" — cron job (auto-create agent if needed)
        """
        parts = session_key.split(":")

        # Meeting session: session:<id>:<agent_id>
        if len(parts) >= 3 and parts[0] == "session":
            agent_id = parts[2]
            agent = self.registry.get(agent_id)
            if agent:
                return agent

        # Cron job: cron:<persona> — create agent on-the-fly
        if len(parts) >= 2 and parts[0] == "cron":
            persona = parts[1]
            agent_id = f"cron-{persona}"
            agent = self.registry.get(agent_id)
            if not agent:
                logger.info(f"Creating cron agent: {agent_id} ({persona})")
                agent = self.registry.create(agent_id=agent_id, persona=persona)
            return agent

        # Fallback: return first registered agent
        for agent_id in self.registry.list():
            return self.registry.get(agent_id)

        return None

    def _merge_messages(self, messages: list[QueuedMessage]) -> str:
        """Merge collected messages into a single input string.

        Single message → return as-is.
        Multiple messages → join with spaces (debounce already grouped them logically).
        """
        if not messages:
            return ""
        if len(messages) == 1:
            return messages[0].content
        return " ".join(m.content for m in messages)

    async def _emit_output(self, session_key: str, output: AgentOutput) -> None:
        """Send agent output to all registered listeners for this session."""
        listeners = self._output_listeners.get(session_key, [])
        for listener in listeners:
            try:
                await listener(output)
            except Exception as e:
                logger.error(f"Output listener error [{session_key}]: {e}")

    def _persist_transcript(
        self,
        session_key: str,
        run_id: str,
        input_text: str,
        response: str,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        """Append run to session transcript JSONL file.

        File: ~/.lexicon/sessions/<agent_id>/transcript.jsonl
        Each line is a JSON object representing one complete agent run.
        """
        parts = session_key.split(":")
        agent_id = parts[2] if len(parts) >= 3 else "unknown"

        session_dir = SESSIONS_DIR / agent_id
        session_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = session_dir / "transcript.jsonl"

        entry = {
            "run_id": run_id,
            "session_key": session_key,
            "timestamp": time.time(),
            "input": input_text,
            "response": response,
            "tool_calls": tool_calls,
        }

        with open(transcript_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        logger.debug(f"Persisted transcript for run {run_id}")
