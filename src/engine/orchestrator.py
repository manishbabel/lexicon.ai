"""Orchestrator — Chief Agent → Sub-Agent routing (OpenClaw-inspired).

The orchestrator is the engine behind the `route_to_agent` tool.
When the Chief Agent decides a sub-agent should handle a task,
it calls route_to_agent(). The orchestrator:

1. Resolves the target agent (workspace + skills + tools)
2. Creates an isolated sub-agent runtime (fresh messages, shared vault)
3. Injects delegation context into the sub-agent's prompt
4. Runs the sub-agent (tool calling loop)
5. Collects the result and returns it to the Chief
6. Disposes the temporary runtime

Sub-agents are ONESHOT by default — fresh runtime per delegation,
no persistent state. This keeps them fast and context-clean.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.shared.constants import BUNDLED_WORKSPACES
from src.shared.logger import get_logger
from src.shared.types import AgentConfig, AgentOutput

from .llm.router import PersonaLLMRouter
from .llm.provider import LLMProvider
from .memory.manager import MemoryManager
from .runtime import AgentRuntime
from .skills import SkillRegistry
from .tools.registry import ToolRegistry

from .registry import AGENT_TOOL_ALLOWLIST

logger = get_logger("lexicon.engine.orchestrator")

# Max sub-agent response length (chars) to prevent runaway output
MAX_SUBAGENT_RESPONSE_CHARS = 8000

# Max concurrent sub-agent runs (uses queue's subagent lane in future)
MAX_CONCURRENT_SUBAGENTS = 4


class Orchestrator:
    """Manages Chief → Sub-Agent delegation.

    The orchestrator sits between the Chief Agent and the sub-agent runtimes.
    It creates isolated runtimes on demand, runs them, and returns results.

    Usage:
        orchestrator = Orchestrator(llm=provider, tool_registry=tools)
        # Register as a tool on the Chief Agent:
        chief_runtime.register_tool(..., handler=orchestrator.route_to_agent)
    """

    def __init__(
        self,
        llm: LLMProvider | None,
        tool_registry: ToolRegistry,
        llm_router: PersonaLLMRouter | None = None,
    ):
        self._llm = llm
        self._tool_registry = tool_registry
        self._llm_router = llm_router or PersonaLLMRouter()

        # Skill registries per persona (cached — loaded once, reused)
        self._skill_registries: dict[str, SkillRegistry] = {}

        # Track active sub-agent runs for concurrency control
        self._active_runs: set[str] = set()

        logger.info("Orchestrator initialized")

    # ── Skill Registry Management ─────────────────────────────────

    def _get_skill_registry(self, persona: str) -> SkillRegistry:
        """Get or create a cached skill registry for a persona."""
        if persona not in self._skill_registries:
            registry = SkillRegistry()
            registry.load_all(persona)
            self._skill_registries[persona] = registry
            logger.info(f"Loaded skill registry for persona '{persona}'")
        return self._skill_registries[persona]

    # ── Sub-Agent Creation ────────────────────────────────────────

    def _create_subagent_runtime(
        self,
        agent_id: str,
        persona: str,
        delegation_context: str,
        skill_hints: list[str] | None = None,
    ) -> AgentRuntime:
        """Create an isolated sub-agent runtime for a delegation.

        The runtime is ONESHOT — fresh message history, own tools,
        but shared vault (same Obsidian vault via tools).

        Args:
            agent_id: Unique ID for this sub-agent run
            persona: Which persona to load ("software-engineer", "ai-educator", "doctor")
            delegation_context: Context from Chief injected into system prompt
            skill_hints: Optional list of skill names to prioritize
        """
        workspace_path = str(BUNDLED_WORKSPACES / persona)

        if self._llm is not None:
            llm = self._llm
            provider_name = "custom"
            model_name = getattr(llm, "default_model", None)
            if not model_name:
                raise ValueError(
                    "Model must be provided when using a fixed LLM provider without a default model."
                )
        else:
            resolved = self._llm_router.resolve(persona=persona)
            llm = resolved.provider
            provider_name = resolved.provider_name
            model_name = resolved.model or getattr(llm, "default_model", None)
            if not model_name:
                raise ValueError(
                    f"No model resolved for persona '{persona}'. "
                    "Set a persona model or configure a provider default."
                )

        config = AgentConfig(
            id=agent_id,
            workspace_path=workspace_path,
            persona=persona,
            provider=provider_name,
            model=model_name,
            max_tokens=2048,  # Sub-agents get more tokens for detailed responses
        )

        # Create MemoryManager for the sub-agent (own working memory, shared vault)
        memory = MemoryManager(agent_id=agent_id)

        runtime = AgentRuntime(config=config, llm=llm, memory=memory)

        # Wire tools (filtered by allowlist)
        self._wire_tools(runtime, persona)

        # Wire skills
        skill_registry = self._get_skill_registry(persona)
        if skill_hints:
            # Filter to only hinted skills + always-available ones
            all_metadata = skill_registry.get_metadata()
            filtered = [
                m for m in all_metadata
                if m["name"] in skill_hints or not skill_hints
            ]
            runtime.set_skill_metadata(filtered if filtered else all_metadata)
        else:
            runtime.set_skill_metadata(skill_registry.get_metadata())

        # Inject delegation context as memory context
        # This appears in the system prompt under "# Relevant Knowledge"
        runtime.set_memory_context(delegation_context)

        logger.info(
            f"Created sub-agent runtime: {agent_id} ({persona}) "
            f"provider={config.provider} model={config.model} "
            f"with {len(runtime.tool_definitions)} tools"
        )
        return runtime

    def _wire_tools(self, runtime: AgentRuntime, persona: str) -> None:
        """Wire tools into a sub-agent runtime, filtered by allowlist."""
        allowlist = AGENT_TOOL_ALLOWLIST.get(persona)

        for tool_name in self._tool_registry.list_tools():
            # Skip route_to_agent — sub-agents can't delegate further
            if tool_name == "route_to_agent":
                continue

            # Apply allowlist if set (None = all allowed)
            if allowlist is not None and tool_name not in allowlist:
                continue

            tool_def = self._tool_registry.get(tool_name)
            if tool_def:
                runtime.register_tool(
                    name=tool_def.name,
                    description=tool_def.description,
                    input_schema=tool_def.input_schema,
                    handler=tool_def.handler,
                )

    # ── Delegation Context Builder ────────────────────────────────

    def _build_delegation_context(
        self,
        task: str,
        context: str,
        skills: list[str] | None = None,
    ) -> str:
        """Build the context string injected into the sub-agent's prompt.

        This tells the sub-agent WHY it was called and WHAT to focus on.
        """
        parts = [
            "# Delegation Context",
            f"You were delegated this task by the Chief Agent.",
            "",
            f"## Task",
            task,
        ]

        if context:
            parts.extend([
                "",
                "## Meeting Context",
                context,
            ])

        if skills:
            parts.extend([
                "",
                f"## Suggested Skills: {', '.join(skills)}",
                "Use read_skill() to load these skills for detailed guidance.",
            ])

        parts.extend([
            "",
            "## Response Guidelines",
            "- Be specific and actionable",
            "- Include terms the user can actually say in the meeting",
            "- If suggesting terminology, include ready-to-use sentences",
            "- Keep your response concise — this will be shown in a side panel",
        ])

        return "\n".join(parts)

    # ── The Main Entry Point ──────────────────────────────────────

    async def route_to_agent(
        self,
        agent: str,
        task: str,
        context: str = "",
        skills: list[str] | None = None,
    ) -> str:
        """Route a task to a sub-agent. This is the tool the Chief calls.

        Args:
            agent: Target persona ID ("software-engineer", "ai-educator", "doctor")
            task: What the sub-agent should do
            context: Relevant transcript / meeting context
            skills: Hint — which skills to activate (optional)

        Returns:
            The sub-agent's text response (or error message)
        """
        # Validate persona
        workspace_path = BUNDLED_WORKSPACES / agent
        if not workspace_path.is_dir():
            available = [
                d.name for d in BUNDLED_WORKSPACES.iterdir()
                if d.is_dir() and (d / "AGENT.md").exists()
            ]
            return f"Unknown agent '{agent}'. Available: {available}"

        # Concurrency check
        if len(self._active_runs) >= MAX_CONCURRENT_SUBAGENTS:
            return (
                "Too many sub-agents running. Wait for one to finish. "
                f"Active: {len(self._active_runs)}/{MAX_CONCURRENT_SUBAGENTS}"
            )

        # Create unique run ID
        run_id = f"subagent:{agent}:{uuid.uuid4().hex[:8]}"
        self._active_runs.add(run_id)

        logger.info(
            f"Routing to sub-agent: {agent} | task: {task[:80]}... | "
            f"skills: {skills}"
        )

        try:
            # Build delegation context
            delegation_context = self._build_delegation_context(
                task=task, context=context, skills=skills,
            )

            # Create isolated sub-agent runtime
            runtime = self._create_subagent_runtime(
                agent_id=run_id,
                persona=agent,
                delegation_context=delegation_context,
                skill_hints=skills,
            )

            # Run the sub-agent and collect output
            response = await self._run_subagent(runtime, task)

            logger.info(
                f"Sub-agent {run_id} complete: {len(response)} chars"
            )
            return response

        except Exception as e:
            logger.error(f"Sub-agent {run_id} failed: {e}")
            return f"Sub-agent error: {e}"

        finally:
            self._active_runs.discard(run_id)

    async def _run_subagent(self, runtime: AgentRuntime, task: str) -> str:
        """Execute the sub-agent's agentic loop and collect the text response.

        The sub-agent runs its full tool-calling loop autonomously.
        We collect all text output and return it as a single string.
        """
        response_parts: list[str] = []
        total_chars = 0

        async for output in runtime.run(task):
            if output.type == "text_delta":
                # Enforce max response length
                if total_chars + len(output.delta) > MAX_SUBAGENT_RESPONSE_CHARS:
                    remaining = MAX_SUBAGENT_RESPONSE_CHARS - total_chars
                    if remaining > 0:
                        response_parts.append(output.delta[:remaining])
                    response_parts.append(
                        "\n\n[Response truncated — max length reached]"
                    )
                    break
                response_parts.append(output.delta)
                total_chars += len(output.delta)

            elif output.type == "error":
                return f"Sub-agent error: {output.error}"

            elif output.type == "done":
                break

        return "".join(response_parts)

    # ── State ─────────────────────────────────────────────────────

    @property
    def active_run_count(self) -> int:
        """Number of currently running sub-agents."""
        return len(self._active_runs)

    def get_available_agents(self) -> list[dict[str, str]]:
        """List all available sub-agent personas with descriptions.

        Used by the Chief to know who it can delegate to.
        """
        agents = []
        for child in sorted(BUNDLED_WORKSPACES.iterdir()):
            if not child.is_dir():
                continue
            agent_md = child / "AGENT.md"
            if not agent_md.exists():
                continue

            # Read first line of AGENT.md as description
            content = agent_md.read_text().strip()
            first_line = content.split("\n")[0].strip("# ").strip()

            agents.append({
                "id": child.name,
                "description": first_line,
            })
        return agents
