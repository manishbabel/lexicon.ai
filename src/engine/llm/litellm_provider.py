"""LiteLLM provider — unified wrapper for 100+ LLM providers with fallback.

Uses LiteLLM's Router for:
  - Automatic failover between models/providers
  - Rate limit handling with retries
  - Load balancing across deployments
  - Unified OpenAI-compatible interface for all providers

Replaces separate OpenAI + Claude providers with a single provider.
All messages are in OpenAI format (LiteLLM translates for non-OpenAI backends).
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import litellm
from litellm import Router

from src.shared.config import get_settings
from src.shared.constants import MAX_TOKENS_DEFAULT
from src.shared.logger import get_logger
from src.shared.types import LLMEvent

from .provider import LLMProvider

logger = get_logger("lexicon.engine.llm.litellm")

# Suppress LiteLLM's verbose logging — we use our own
litellm.suppress_debug_info = True


def _build_model_list(settings: Any) -> list[dict[str, Any]]:
    """Build LiteLLM Router model list from settings.

    Each entry maps a model_name (our alias) to a litellm_params dict
    with the actual provider model string and API key.
    """
    models: list[dict[str, Any]] = []

    # OpenAI models
    if settings.openai_api_key:
        for model in ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"]:
            models.append({
                "model_name": model,
                "litellm_params": {
                    "model": model,
                    "api_key": settings.openai_api_key,
                },
            })

    # Anthropic models (LiteLLM prefix: "anthropic/")
    if settings.anthropic_api_key:
        anthropic_models = [
            ("claude-opus-4-6", "anthropic/claude-opus-4-6"),
            ("claude-sonnet-4-6", "anthropic/claude-sonnet-4-6"),
            ("claude-haiku-4-5", "anthropic/claude-haiku-4-5-20251001"),
            # Legacy names
            ("claude-3-5-sonnet", "anthropic/claude-3-5-sonnet-20241022"),
            ("claude-3-5-haiku", "anthropic/claude-3-5-haiku-20241022"),
        ]
        for alias, litellm_model in anthropic_models:
            models.append({
                "model_name": alias,
                "litellm_params": {
                    "model": litellm_model,
                    "api_key": settings.anthropic_api_key,
                },
            })

    return models


def _build_fallback_list(settings: Any) -> list[dict[str, list[str]]]:
    """Build fallback chains based on available API keys.

    If both providers available: gpt-4o → claude-sonnet, claude → gpt-4o
    If only one: no fallback needed.
    """
    fallbacks: list[dict[str, list[str]]] = []

    has_openai = bool(settings.openai_api_key)
    has_anthropic = bool(settings.anthropic_api_key)

    if has_openai and has_anthropic:
        fallbacks = [
            {"gpt-4o": ["claude-sonnet-4-6"]},
            {"gpt-4o-mini": ["claude-haiku-4-5"]},
            {"claude-sonnet-4-6": ["gpt-4o"]},
            {"claude-haiku-4-5": ["gpt-4o-mini"]},
            {"claude-opus-4-6": ["gpt-4o"]},
        ]

    return fallbacks


# ── Message format conversion ───────────────────────────────────────
# LiteLLM uses OpenAI message format. These are the same converters
# from openai_provider.py — kept here so the old files can be deleted.

def _convert_messages(
    system: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert internal (Anthropic-style) messages to OpenAI format."""
    oai_messages: list[dict[str, Any]] = []

    if system:
        oai_messages.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if isinstance(content, str):
            oai_messages.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
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
        else:
            oai_messages.append({"role": role, "content": str(content)})

    return oai_messages


def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic-style tool definitions to OpenAI format."""
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


# ── Provider ─────────────────────────────────────────────────────────

class LiteLLMProvider(LLMProvider):
    """Unified LLM provider using LiteLLM Router.

    Supports all LiteLLM-compatible providers (OpenAI, Anthropic, Cohere,
    Mistral, Ollama, etc.) with automatic fallback and retry.
    """

    def __init__(
        self,
        default_model: str | None = None,
        model_list: list[dict[str, Any]] | None = None,
        fallbacks: list[dict[str, list[str]]] | None = None,
    ):
        settings = get_settings()
        self._model_list = model_list or _build_model_list(settings)
        self._fallbacks = fallbacks or _build_fallback_list(settings)
        self.default_model = default_model or settings.default_llm_model or "gpt-4o"

        if not self._model_list:
            raise RuntimeError(
                "No LLM API keys configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY."
            )

        self._router = Router(
            model_list=self._model_list,
            fallbacks=self._fallbacks,
            retry_after=5,       # seconds before retry on rate limit
            num_retries=2,       # retries per model before fallback
            timeout=60,          # seconds per request
            routing_strategy="simple-shuffle",
        )

        available = {m["model_name"] for m in self._model_list}
        logger.info(
            f"LiteLLM provider initialized: {len(self._model_list)} model deployments, "
            f"models: {sorted(available)}, "
            f"fallback chains: {len(self._fallbacks)}"
        )

    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = MAX_TOKENS_DEFAULT,
    ) -> AsyncIterator[LLMEvent]:
        """Stream response via LiteLLM Router with automatic fallback."""
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

        current_tool_calls: dict[int, dict[str, Any]] = {}

        response = await self._router.acompletion(**kwargs)

        async for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue

            delta = choice.delta

            # Text content
            if delta and delta.content:
                yield LLMEvent(type="text_delta", text=delta.content)

            # Tool calls (streamed across chunks)
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
                if choice.finish_reason in ("tool_calls", "stop"):
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
        """Non-streaming completion via LiteLLM Router."""
        oai_messages = _convert_messages(system, messages)

        response = await self._router.acompletion(
            model=model or self.default_model,
            max_tokens=max_tokens,
            messages=oai_messages,
        )

        return response.choices[0].message.content or ""

    @property
    def available_models(self) -> list[str]:
        """List model names available in this router."""
        return sorted({m["model_name"] for m in self._model_list})
