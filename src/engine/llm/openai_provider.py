"""OpenAI LLM provider with streaming and tool-use support.

Translates between the internal message format (Anthropic-style) and
OpenAI's API format. The runtime doesn't need to know which provider
is being used.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import openai

from src.shared.config import get_settings
from src.shared.constants import MAX_TOKENS_DEFAULT
from src.shared.logger import get_logger
from src.shared.types import LLMEvent

from .provider import LLMProvider

logger = get_logger("lexicon.engine.llm.openai")

# Default OpenAI model
DEFAULT_OPENAI_MODEL = "gpt-4o"


def _convert_messages(
    system: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert internal (Anthropic-style) messages to OpenAI format.

    Key differences:
    - System prompt becomes a system message (not a separate param)
    - Tool use blocks in assistant messages become tool_calls
    - Tool results become role="tool" messages with tool_call_id
    - Content arrays with tool_result entries need special handling
    """
    oai_messages: list[dict[str, Any]] = []

    # System message first
    if system:
        oai_messages.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        # Simple string content
        if isinstance(content, str):
            oai_messages.append({"role": role, "content": content})
            continue

        # Content is a list (Anthropic-style blocks)
        if isinstance(content, list):
            # Assistant message with tool_use blocks
            if role == "assistant":
                tool_calls = []
                text_parts = []

                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block["id"],
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block.get("input", {})),
                                },
                            })
                        elif block.get("type") == "text":
                            text_parts.append(block.get("text", ""))

                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if text_parts:
                    assistant_msg["content"] = "".join(text_parts)
                else:
                    assistant_msg["content"] = None
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                oai_messages.append(assistant_msg)

            # User message with tool_result blocks
            elif role == "user":
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        oai_messages.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": str(block.get("content", "")),
                        })
                    elif isinstance(block, dict) and block.get("type") == "text":
                        oai_messages.append({"role": "user", "content": block.get("text", "")})
                    elif isinstance(block, str):
                        oai_messages.append({"role": "user", "content": block})

        # Fallback
        else:
            oai_messages.append({"role": role, "content": str(content)})

    return oai_messages


def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic-style tool definitions to OpenAI format.

    Anthropic: {"name": ..., "description": ..., "input_schema": {...}}
    OpenAI:    {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for tool in tools
    ]


class OpenAIProvider(LLMProvider):
    """OpenAI provider using the Chat Completions API with streaming."""

    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        settings = get_settings()
        self.client = openai.AsyncOpenAI(
            api_key=api_key or settings.openai_api_key,
        )
        self.default_model = default_model or DEFAULT_OPENAI_MODEL

    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = MAX_TOKENS_DEFAULT,
    ) -> AsyncIterator[LLMEvent]:
        """Stream response from OpenAI.

        Converts messages/tools from Anthropic format, streams response,
        and yields LLMEvent objects matching the internal interface.
        """
        oai_messages = _convert_messages(system, messages)
        use_model = model or self.default_model

        kwargs: dict[str, Any] = {
            "model": use_model,
            "max_tokens": max_tokens,
            "messages": oai_messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = _convert_tools(tools)

        # Track tool calls being assembled across chunks
        current_tool_calls: dict[int, dict[str, Any]] = {}

        stream = await self.client.chat.completions.create(**kwargs)
        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue

            delta = choice.delta

            # Text content
            if delta and delta.content:
                yield LLMEvent(type="text_delta", text=delta.content)

            # Tool calls (may arrive across multiple chunks)
            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index

                    if idx not in current_tool_calls:
                        current_tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": "",
                            "arguments": "",
                        }

                    if tc.id:
                        current_tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            current_tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            current_tool_calls[idx]["arguments"] += tc.function.arguments

            # Finish reason
            if choice.finish_reason:
                # Emit any completed tool calls
                if choice.finish_reason == "tool_calls":
                    for idx in sorted(current_tool_calls.keys()):
                        tc_data = current_tool_calls[idx]
                        try:
                            tool_input = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                        except json.JSONDecodeError:
                            tool_input = {}

                        yield LLMEvent(
                            type="tool_use",
                            name=tc_data["name"],
                            input=tool_input,
                            raw={
                                "type": "tool_use",
                                "id": tc_data["id"],
                                "name": tc_data["name"],
                                "input": tool_input,
                            },
                        )
                    current_tool_calls.clear()

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
        oai_messages = _convert_messages(system, messages)

        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            messages=oai_messages,
        )

        return response.choices[0].message.content or ""
