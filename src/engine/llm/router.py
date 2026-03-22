"""Persona-aware LLM routing.

Resolves which provider + model a persona should use.
This keeps AgentRuntime provider-agnostic while allowing Chief,
ai-educator, and other personas to use different backends.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.config import get_settings
from src.shared.logger import get_logger

from .provider import LLMProvider

logger = get_logger("lexicon.engine.llm.router")


@dataclass
class ResolvedLLM:
    provider_name: str
    model: str | None
    provider: LLMProvider


class PersonaLLMRouter:
    """Resolve an LLM provider + model for a given persona.

    Provider instances are cached per backend name and reused across personas.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._providers: dict[str, LLMProvider] = {}

    def resolve(
        self,
        persona: str,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> ResolvedLLM:
        """Resolve provider + model for a persona with optional overrides."""
        provider_name = self._normalize_provider(
            provider or self._provider_for_persona(persona) or self._settings.default_llm_provider
        )
        model_name = model or self._model_for_persona(persona) or self._settings.default_llm_model or None
        if provider_name == "anthropic" and not model_name:
            raise ValueError(
                f"No model configured for persona '{persona}' with provider 'anthropic'. "
                f"Set {persona.replace('-', '_')}_llm_model or default_llm_model."
            )
        provider_instance = self._get_provider(provider_name)

        logger.info(
            f"Resolved LLM for persona '{persona}': provider={provider_name}, "
            f"model={model_name or '(provider default)'}"
        )

        return ResolvedLLM(
            provider_name=provider_name,
            model=model_name,
            provider=provider_instance,
        )

    def _provider_for_persona(self, persona: str) -> str:
        field_name = f"{persona.replace('-', '_')}_llm_provider"
        return getattr(self._settings, field_name, "")

    def _model_for_persona(self, persona: str) -> str:
        field_name = f"{persona.replace('-', '_')}_llm_model"
        return getattr(self._settings, field_name, "")

    def _get_provider(self, provider_name: str) -> LLMProvider:
        if provider_name in self._providers:
            return self._providers[provider_name]

        if provider_name == "litellm":
            from .litellm_provider import LiteLLMProvider

            provider = LiteLLMProvider()
        elif provider_name == "openai":
            from .openai_provider import OpenAIProvider

            provider = OpenAIProvider()
        elif provider_name in {"anthropic", "claude"}:
            try:
                from .claude_provider import ClaudeProvider
            except ImportError as exc:
                raise RuntimeError(
                    "Anthropic provider requested but the anthropic package is not installed."
                ) from exc
            provider = ClaudeProvider()
            provider_name = "anthropic"
        else:
            raise ValueError(
                f"Unknown LLM provider '{provider_name}'. "
                "Supported: litellm, openai, anthropic"
            )

        self._providers[provider_name] = provider
        return provider

    def _normalize_provider(self, provider_name: str) -> str:
        normalized = provider_name.strip().lower()
        if normalized == "claude":
            return "anthropic"
        return normalized
