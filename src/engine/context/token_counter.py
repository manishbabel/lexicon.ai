"""Token counter + budget allocation for context management.

Pre-send estimation — we need to know how many tokens the context
will use BEFORE sending to the LLM, so we can prune/compact to fit.

Uses a simple chars/4 heuristic by default. Accurate enough for
budget decisions. LangSmith handles precise post-send tracking.

Model context windows:
  - gpt-4o:        128k tokens
  - claude-sonnet:  200k tokens
  - claude-haiku:   200k tokens
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.context.token_counter")

# Chars-per-token estimate. Conservative — slightly overestimates
# to avoid going over budget. Real ratio is ~3.5-4.5 depending on content.
CHARS_PER_TOKEN = 4

# Model context windows (tokens)
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    "claude-opus-4-6": 200_000,
}

# Default if model not in the map
DEFAULT_CONTEXT_WINDOW = 128_000

# Reserve tokens for the LLM's response
RESPONSE_RESERVE_TOKENS = 4096


@dataclass
class TokenBudget:
    """Token budget allocation for context assembly.

    Splits the available context window across sections with
    configurable proportions.
    """
    total: int  # Total available tokens (context window - response reserve)
    system_prompt: int = 0  # IDENTITY + SOUL + AGENT
    skills: int = 0  # Skill metadata
    memory: int = 0  # Memory context (from MemoryManager)
    messages: int = 0  # Conversation history
    used: dict[str, int] = field(default_factory=dict)  # Actual usage per section

    @property
    def remaining(self) -> int:
        """Tokens remaining after all sections."""
        return self.total - sum(self.used.values())

    @property
    def messages_remaining(self) -> int:
        """Tokens remaining for messages after fixed sections."""
        fixed = (
            self.used.get("system_prompt", 0)
            + self.used.get("skills", 0)
            + self.used.get("memory", 0)
        )
        return self.total - fixed

    def is_over_budget(self) -> bool:
        return sum(self.used.values()) > self.total


class TokenCounter:
    """Estimates token counts and manages budget allocation.

    Usage:
        counter = TokenCounter(model="gpt-4o")

        # Estimate tokens for a string
        tokens = counter.count("Hello world")

        # Estimate tokens for messages list
        tokens = counter.count_messages(messages)

        # Create a budget for context assembly
        budget = counter.create_budget(
            system_prompt="...",
            skills_text="...",
            memory_context="...",
            messages=[...],
        )
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.context_window = MODEL_CONTEXT_WINDOWS.get(
            model, DEFAULT_CONTEXT_WINDOW,
        )
        self.max_input_tokens = self.context_window - RESPONSE_RESERVE_TOKENS

    def count(self, text: str) -> int:
        """Estimate token count for a string.

        Uses chars/4 heuristic. Good enough for budget decisions.
        """
        if not text:
            return 0
        return max(1, len(text) // CHARS_PER_TOKEN)

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        """Estimate token count for a list of messages.

        Handles both string content and structured content (tool_use, tool_result).
        Adds per-message overhead for role tokens etc.
        """
        total = 0
        for msg in messages:
            # Per-message overhead (role, formatting)
            total += 4

            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.count(content)
            elif isinstance(content, list):
                # Structured content (tool_use blocks, tool_result blocks)
                for block in content:
                    if isinstance(block, dict):
                        # Serialize to string for estimation
                        total += self.count(json.dumps(block, default=str))
                    elif isinstance(block, str):
                        total += self.count(block)
            else:
                total += self.count(str(content))

        return total

    def create_budget(
        self,
        system_prompt: str = "",
        skills_text: str = "",
        memory_context: str = "",
        messages: list[dict[str, Any]] | None = None,
    ) -> TokenBudget:
        """Create a token budget with actual usage per section.

        Returns a budget object showing how tokens are allocated
        and how much room remains for messages.
        """
        budget = TokenBudget(total=self.max_input_tokens)

        budget.used["system_prompt"] = self.count(system_prompt)
        budget.used["skills"] = self.count(skills_text)
        budget.used["memory"] = self.count(memory_context)
        budget.used["messages"] = self.count_messages(messages or [])

        # Log if over budget
        if budget.is_over_budget():
            total_used = sum(budget.used.values())
            logger.warning(
                f"Context over budget: {total_used}/{budget.total} tokens. "
                f"Breakdown: {budget.used}"
            )

        return budget

    def fits(self, text: str, budget_remaining: int) -> bool:
        """Check if text fits within remaining budget."""
        return self.count(text) <= budget_remaining
