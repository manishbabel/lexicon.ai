"""Anthropic Claude LLM provider with streaming support."""

from __future__ import annotations

from typing import Any, AsyncIterator

import anthropic

from src.shared.config import get_settings
from src.shared.constants import MAX_TOKENS_DEFAULT
from src.shared.logger import get_logger
from src.shared.types import LLMEvent

from .provider import LLMProvider

logger = get_logger("lexicon.engine.llm.claude")


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider using the Messages API with streaming."""

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
    ):
        settings = get_settings()
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key,
        )
        self.default_model = default_model

    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = MAX_TOKENS_DEFAULT,
    ) -> AsyncIterator[LLMEvent]:
        """Stream response from Claude.

        Handles text deltas and tool use blocks.
        """
        use_model = model or self.default_model
        if not use_model:
            raise ValueError(
                "No Anthropic model configured. Pass model=... or set a persona/default model."
            )

        kwargs: dict[str, Any] = {
            "model": use_model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        async with self.client.messages.stream(**kwargs) as stream:
            current_tool_name: str | None = None
            current_tool_input_json = ""
            current_tool_id: str | None = None

            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool_name = block.name
                        current_tool_id = block.id
                        current_tool_input_json = ""

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield LLMEvent(type="text_delta", text=delta.text)

                    elif delta.type == "input_json_delta":
                        current_tool_input_json += delta.partial_json

                elif event.type == "content_block_stop":
                    if current_tool_name:
                        import json

                        try:
                            tool_input = json.loads(current_tool_input_json) if current_tool_input_json else {}
                        except json.JSONDecodeError:
                            tool_input = {}

                        yield LLMEvent(
                            type="tool_use",
                            name=current_tool_name,
                            input=tool_input,
                            raw={
                                "type": "tool_use",
                                "id": current_tool_id,
                                "name": current_tool_name,
                                "input": tool_input,
                            },
                        )
                        current_tool_name = None
                        current_tool_input_json = ""
                        current_tool_id = None

                elif event.type == "message_stop":
                    yield LLMEvent(type="stop")

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = MAX_TOKENS_DEFAULT,
    ) -> str:
        """Non-streaming completion."""
        use_model = model or self.default_model
        if not use_model:
            raise ValueError(
                "No Anthropic model configured. Pass model=... or set a persona/default model."
            )

        response = await self.client.messages.create(
            model=use_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        # Extract text from content blocks
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "".join(text_parts)
