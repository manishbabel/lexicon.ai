"""Tool registry — manages tools available to agent runtimes.

Tools are registered here, then wired into AgentRuntime via register_tool().
Each tool has a name, description, JSON schema, and async handler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.tools.registry")


@dataclass
class ToolDef:
    """A tool definition."""
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Coroutine[Any, Any, Any]]


class ToolRegistry:
    """Central registry for agent tools.

    Tools registered here can be bulk-wired into any AgentRuntime.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Coroutine[Any, Any, Any]],
    ) -> None:
        """Register a tool."""
        self._tools[name] = ToolDef(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
        )
        logger.info(f"Registered tool: {name}")

    def get(self, name: str) -> ToolDef | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def wire_into_runtime(self, runtime: Any) -> None:
        """Register all tools into an AgentRuntime instance.

        Calls runtime.register_tool() for each tool in the registry.
        """
        for tool in self._tools.values():
            runtime.register_tool(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                handler=tool.handler,
            )
        logger.info(f"Wired {len(self._tools)} tools into runtime {getattr(runtime, 'config', {})}")
