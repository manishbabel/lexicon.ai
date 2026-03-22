"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from src.shared.types import LLMEvent


class LLMProvider(ABC):
    """Base class for LLM providers (Claude, OpenAI, etc.)."""

    @abstractmethod
    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> AsyncIterator[LLMEvent]:
        """Stream a response from the LLM.

        Yields LLMEvent objects:
          - type="text_delta": partial text output
          - type="tool_use": the LLM wants to call a tool
          - type="stop": generation complete
        """
        ...

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Non-streaming completion. Returns full text response."""
        ...
