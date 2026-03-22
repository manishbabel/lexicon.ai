"""Agent registry — create, get, list agent runtimes."""

from __future__ import annotations

from src.shared.constants import BUNDLED_WORKSPACES
from src.shared.logger import get_logger
from src.shared.types import AgentConfig

from .llm.router import PersonaLLMRouter
from .llm.provider import LLMProvider
from .runtime import AgentRuntime
from .skills import SkillRegistry
from .tools.registry import ToolRegistry

logger = get_logger("lexicon.engine.registry")

# Per-persona tool allowlists.
# Chief only gets route_to_agent (delegates, never calls tools directly).
# Sub-agents get everything EXCEPT route_to_agent.
# None = all tools allowed (after filtering route_to_agent for sub-agents).
AGENT_TOOL_ALLOWLIST: dict[str, list[str] | None] = {
    "chief": ["route_to_agent"],
    "software-engineer": None,
    "ai-educator": None,
    "doctor": None,
}


class AgentRegistry:
    """Manages AgentRuntime instances by agent ID."""

    def __init__(
        self,
        llm: LLMProvider | None = None,
        llm_router: PersonaLLMRouter | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self._agents: dict[str, AgentRuntime] = {}
        self._llm = llm
        self._llm_router = llm_router or PersonaLLMRouter()
        self._tool_registry = tool_registry
        # One skill registry per persona (shared across agents of same persona)
        self._skill_registries: dict[str, SkillRegistry] = {}

    def _get_skill_registry(self, persona: str) -> SkillRegistry:
        """Get or create a skill registry for a persona."""
        if persona not in self._skill_registries:
            registry = SkillRegistry()
            registry.load_all(persona)
            self._skill_registries[persona] = registry
            logger.info(f"Created skill registry for persona '{persona}'")
        return self._skill_registries[persona]

    def create(
        self,
        agent_id: str,
        persona: str,
        workspace_path: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> AgentRuntime:
        """Create and register a new agent runtime.

        Automatically loads skills for the persona and wires them
        into the runtime via set_skill_metadata().
        """
        if agent_id in self._agents:
            logger.warning(f"Agent {agent_id} already exists, returning existing")
            return self._agents[agent_id]

        # Default workspace path: bundled templates
        if workspace_path is None:
            workspace_path = str(BUNDLED_WORKSPACES / persona)

        if self._llm is not None:
            llm = self._llm
            provider_name = provider or "custom"
            resolved_model = model or getattr(llm, "default_model", None)
            if not resolved_model:
                raise ValueError(
                    "Model must be provided when using a fixed LLM provider without a default model."
                )
        else:
            resolved = self._llm_router.resolve(
                persona=persona,
                provider=provider,
                model=model,
            )
            llm = resolved.provider
            provider_name = resolved.provider_name
            resolved_model = resolved.model or getattr(llm, "default_model", None)
            if not resolved_model:
                raise ValueError(
                    f"No model resolved for persona '{persona}'. "
                    "Set a persona model or configure a provider default."
                )

        config = AgentConfig(
            id=agent_id,
            workspace_path=workspace_path,
            persona=persona,
            provider=provider_name,
            model=resolved_model,
            max_tokens=max_tokens,
        )

        runtime = AgentRuntime(config=config, llm=llm)

        # Wire tools into the runtime (filtered by persona allowlist)
        if self._tool_registry:
            self._wire_tools(runtime, persona)

        # Load and wire skills for this persona
        skill_registry = self._get_skill_registry(persona)
        runtime.set_skill_metadata(skill_registry.get_metadata())

        self._agents[agent_id] = runtime
        logger.info(
            f"Registered agent: {agent_id} ({persona}) "
            f"provider={config.provider} model={config.model}"
        )
        return runtime

    def _wire_tools(self, runtime: AgentRuntime, persona: str) -> None:
        """Wire tools into a runtime, filtered by persona allowlist."""
        allowlist = AGENT_TOOL_ALLOWLIST.get(persona)

        wired = 0
        for tool_name in self._tool_registry.list_tools():
            # If allowlist is set, only wire allowed tools
            if allowlist is not None and tool_name not in allowlist:
                continue

            # Sub-agents (allowlist=None) get everything except route_to_agent
            if allowlist is None and tool_name == "route_to_agent":
                continue

            tool_def = self._tool_registry.get(tool_name)
            if tool_def:
                runtime.register_tool(
                    name=tool_def.name,
                    description=tool_def.description,
                    input_schema=tool_def.input_schema,
                    handler=tool_def.handler,
                )
                wired += 1

        logger.info(f"Wired {wired} tools into {persona} agent (allowlist={allowlist})")

    def get(self, agent_id: str) -> AgentRuntime | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def list(self) -> list[str]:
        """List all registered agent IDs."""
        return list(self._agents.keys())

    def remove(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Removed agent: {agent_id}")
            return True
        return False
