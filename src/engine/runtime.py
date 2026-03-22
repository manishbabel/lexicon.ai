"""AgentRuntime — core agentic execution loop (OpenClaw-inspired).

The LLM decides what tools to call, how many times, and when to stop.
We give it tools + instructions — it figures out the path.

Enhancements over basic loop:
- Lazy skill loading: metadata in prompt, read on demand via read_skill tool
- Context engine: token budgeting, pruning (tool results), compaction (LLM summary)
- Merged steering: drain all pending chunks into one labeled message
- Response persistence: assistant output appended to working memory
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

from src.shared.logger import get_logger
from src.shared.types import AgentConfig, AgentOutput, LLMEvent, WorkspaceContext

from .context.compactor import Compactor
from .context.pruner import ContextPruner
from .context.token_counter import TokenCounter
from .llm.provider import LLMProvider
from .memory.manager import MemoryManager
from .workspace import build_system_prompt, load_workspace

logger = get_logger("lexicon.engine.runtime")


class AgentRuntime:
    """Runs a single agent: loads workspace, manages conversation, streams responses.

    The agentic loop:
    1. Build system prompt (workspace + skill metadata + memory context)
    2. Send messages to LLM (streaming)
    3. LLM decides:
       - text → yield to client
       - tool_use → execute → check steering queue → loop back to LLM
       - stop → done
    4. The LLM controls the path — not the developer

    Context management:
    - Token counter estimates usage before sending to LLM
    - Pruner truncates large tool results when approaching budget
    - Compactor summarizes old messages via LLM when pruning isn't enough
    """

    def __init__(
        self,
        config: AgentConfig,
        llm: LLMProvider,
        tools: dict[str, Any] | None = None,
        memory: MemoryManager | None = None,
    ):
        self.config = config
        self.llm = llm
        self.tools = tools or {}  # name → async callable
        self.tool_definitions: list[dict[str, Any]] = []  # Anthropic tool format

        # Workspace (IDENTITY.md + SOUL.md + AGENT.md)
        self.workspace: WorkspaceContext = load_workspace(config.workspace_path)

        # Lazy skills: only metadata in prompt, full content via read_skill tool
        self._skill_metadata: list[dict[str, str]] = []  # [{name, description, path}]
        self._skill_cache: dict[str, str] = {}  # name → full SKILL.md content (loaded on demand)

        # Working memory: conversation history
        self._messages: list[dict[str, Any]] = []

        # Memory manager: searches all 4 layers, stores interactions
        self._memory = memory

        # Context engine: token counting, pruning, compaction
        self._token_counter = TokenCounter(model=config.model)
        self._pruner = ContextPruner(counter=self._token_counter)
        self._compactor = Compactor(llm=llm, counter=self._token_counter)

        # Steering queue: transcript chunks injected at tool boundaries
        self._steering_queue: asyncio.Queue[str] = asyncio.Queue()

        # Memory context: injected into system prompt (set by MemoryManager later)
        self._memory_context: str = ""

        # Register the built-in read_skill tool
        self._register_read_skill_tool()

        logger.info(f"AgentRuntime created: {config.id} ({config.persona})")

    # ── Tool Registration ──────────────────────────────────────────

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Any,
    ) -> None:
        """Register a tool the agent can call."""
        self.tools[name] = handler
        self.tool_definitions.append({
            "name": name,
            "description": description,
            "input_schema": input_schema,
        })

    def _register_read_skill_tool(self) -> None:
        """Register the built-in read_skill tool for lazy skill loading."""
        self.register_tool(
            name="read_skill",
            description=(
                "Read the full instructions for a skill. "
                "Call this when you need detailed guidance for a specific task. "
                "Pass the skill name from the available skills list."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The skill name to read",
                    },
                },
                "required": ["name"],
            },
            handler=self._handle_read_skill,
        )

    async def _handle_read_skill(self, name: str) -> str:
        """Load a skill's full content on demand."""
        if name in self._skill_cache:
            return self._skill_cache[name]

        for skill in self._skill_metadata:
            if skill["name"] == name:
                path = Path(skill["path"])
                if path.exists():
                    content = path.read_text().strip()
                    self._skill_cache[name] = content
                    logger.debug(f"Lazy-loaded skill: {name} ({len(content)} chars)")
                    return content
                return f"Skill file not found: {path}"

        available = [s["name"] for s in self._skill_metadata]
        return f"Unknown skill: {name}. Available: {available}"

    # ── Skill Management ───────────────────────────────────────────

    def set_skill_metadata(self, skills: list[dict[str, str]]) -> None:
        """Set available skills (metadata only — agent reads full content via read_skill).

        Each skill: {"name": "...", "description": "...", "path": "/path/to/SKILL.md"}
        """
        self._skill_metadata = skills
        self._skill_cache.clear()
        logger.info(f"Set {len(skills)} skills for agent {self.config.id}")

    def _build_skills_section(self) -> str | None:
        """Build skills metadata for the system prompt."""
        if not self._skill_metadata:
            return None

        lines = [
            "# Available Skills",
            "Use read_skill(name) to load full instructions when needed.",
            "",
        ]
        for skill in self._skill_metadata:
            lines.append(f"- **{skill['name']}**: {skill.get('description', '')}")
        return "\n".join(lines)

    # ── Memory Context ─────────────────────────────────────────────

    def set_memory_context(self, context: str) -> None:
        """Set memory context injected into system prompt (by MemoryManager)."""
        self._memory_context = context

    # ── Steering ───────────────────────────────────────────────────

    def inject_transcript(self, text: str) -> None:
        """Inject a transcript chunk into the steering queue.

        Called by the runner's steer callback when new audio arrives mid-run.
        Chunks are drained and merged at the next tool boundary.
        """
        self._steering_queue.put_nowait(text)

    def _drain_steering(self) -> str | None:
        """Drain all pending steering chunks into a single merged string.

        Returns None if queue is empty.
        """
        chunks: list[str] = []
        while not self._steering_queue.empty():
            chunks.append(self._steering_queue.get_nowait())
        if not chunks:
            return None
        return " ".join(chunks)

    # ── Context Management ─────────────────────────────────────────

    async def _manage_context(self, system_prompt: str) -> None:
        """Prune and compact messages to fit within token budget.

        Called before each LLM call. Replaces the old _evict_if_needed().

        Two stages:
        1. Prune: truncate/clear large tool results (no LLM call, fast)
        2. Compact: summarize old messages via LLM (if pruning wasn't enough)
        """
        budget = self._token_counter.create_budget(
            system_prompt=system_prompt,
            skills_text=self._build_skills_section() or "",
            memory_context=self._memory_context,
            messages=self._messages,
        )

        messages_budget = budget.messages_remaining

        # Stage 1: Prune tool results
        prune_result = self._pruner.prune(self._messages, messages_budget)
        self._messages = prune_result.messages

        # Stage 2: Compact via LLM (if still over budget)
        self._messages = await self._compactor.compact_if_needed(
            self._messages, messages_budget,
        )

    # ── The Agentic Loop ───────────────────────────────────────────

    async def run(self, input_text: str) -> AsyncIterator[AgentOutput]:
        """Execute the agentic loop for a given input.

        The LLM controls the flow — it decides which tools to call,
        how many times to loop, and when to stop. We just execute
        its decisions and inject steering updates.

        Yields AgentOutput events (text_delta, tool_result, done, error).
        """
        # Recall relevant memory context before building prompt
        if self._memory:
            try:
                self._memory_context = await self._memory.recall(input_text)
                self._memory.store_interaction(input_text, "")  # store input now, response later
            except Exception as e:
                logger.warning(f"Memory recall failed: {e}")

        # Build system prompt from workspace + skill metadata + memory
        skills_section = self._build_skills_section()
        extra_sections = [skills_section] if skills_section else None

        system_prompt = build_system_prompt(
            workspace=self.workspace,
            skills=extra_sections,
            memory_context=self._memory_context or None,
        )

        # Fire agent:start hook
        try:
            from src.engine.hooks.registry import trigger_hook
            await trigger_hook("agent:start", {
                "agent_id": self.config.id,
                "persona": self.config.persona,
                "input": input_text[:200],
            })
        except Exception:
            pass  # hooks are best-effort

        # Add user input to working memory
        self._messages.append({"role": "user", "content": input_text})

        # Context management: prune + compact to fit budget
        await self._manage_context(system_prompt)

        # Accumulate text output for this run (saved to working memory at end)
        run_text = ""

        # ── The loop: may iterate multiple times for tool calls ──
        while True:
            tool_used = False

            async for event in self.llm.stream(
                system=system_prompt,
                messages=self._messages,
                tools=self.tool_definitions if self.tool_definitions else None,
                model=self.config.model,
                max_tokens=self.config.max_tokens,
            ):
                # Text output → stream to client
                if event.type == "text_delta":
                    yield AgentOutput(type="text_delta", delta=event.text)
                    run_text += event.text

                # Tool call → execute → steer → loop back
                elif event.type == "tool_use":
                    tool_used = True
                    tool_name = event.name
                    tool_input = event.input or {}

                    logger.info(f"Tool call: {tool_name}({tool_input})")

                    # Execute
                    if tool_name in self.tools:
                        try:
                            result = await self.tools[tool_name](**tool_input)
                            result_str = str(result)
                        except Exception as e:
                            logger.error(f"Tool {tool_name} failed: {e}")
                            result_str = f"Error: {e}"
                    else:
                        result_str = f"Unknown tool: {tool_name}"

                    yield AgentOutput(
                        type="tool_result",
                        tool_name=tool_name,
                        tool_input=tool_input,
                        tool_result=result_str,
                    )

                    # Append tool use + result to working memory
                    self._messages.append({
                        "role": "assistant",
                        "content": [event.raw],
                    })
                    self._messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": event.raw["id"],
                            "content": result_str,
                        }],
                    })

                    # ═══════════════════════════════════════════
                    # STEERING — drain all chunks, merge into one
                    # ═══════════════════════════════════════════
                    steered = self._drain_steering()
                    if steered:
                        self._messages.append({
                            "role": "user",
                            "content": (
                                "[LIVE TRANSCRIPT UPDATE — conversation has moved on]: "
                                + steered
                            ),
                        })
                        logger.info(f"Steered into run: {steered[:80]}...")

                    # Context management after tool calls
                    await self._manage_context(system_prompt)

                    # Break inner for-loop → re-enter while True for next LLM call
                    break

                # Stop → LLM is done
                elif event.type == "stop":
                    if run_text:
                        self._messages.append({
                            "role": "assistant",
                            "content": run_text,
                        })
                    await self._store_response(run_text)
                    yield AgentOutput(type="done")
                    return

            # If no tool was used and no explicit stop, we're done
            if not tool_used:
                if run_text:
                    self._messages.append({
                        "role": "assistant",
                        "content": run_text,
                    })
                await self._store_response(run_text)
                yield AgentOutput(type="done")
                return

    # ── Memory Helpers ──────────────────────────────────────────────

    async def _store_response(self, response: str) -> None:
        """Store assistant response in memory and fire agent:done hook."""
        if self._memory and response:
            try:
                self._memory.working.add(response, role="assistant", source="conversation")
            except Exception as e:
                logger.warning(f"Failed to store response in memory: {e}")

        # Fire agent:done hook
        try:
            from src.engine.hooks.registry import trigger_hook
            await trigger_hook("agent:done", {
                "agent_id": self.config.id,
                "persona": self.config.persona,
                "memory_manager": self._memory,
                "response_length": len(response) if response else 0,
            })
        except Exception:
            pass  # hooks are best-effort

    def flush_memory(self) -> int:
        """Flush evicted working memory to short-term. Returns count flushed."""
        if self._memory:
            return self._memory.flush()
        return 0

    @property
    def memory(self) -> MemoryManager | None:
        """Access the memory manager (if set)."""
        return self._memory

    # ── State Access ───────────────────────────────────────────────

    def get_messages(self) -> list[dict[str, Any]]:
        """Get current conversation history (working memory)."""
        return list(self._messages)

    def clear_messages(self) -> None:
        """Clear conversation history and skill cache."""
        self._messages.clear()
        self._skill_cache.clear()
