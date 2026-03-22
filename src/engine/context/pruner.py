"""Context pruner — Stage 1: truncate large tool results (no LLM call).

Runs BEFORE compaction. Cheap and fast — just string truncation.
Only prunes tool_result messages. Never touches user or assistant text.

Two stages:
  Soft trim (at 70% budget): truncate large tool results, keep head+tail
  Hard clear (at 90% budget): replace entire tool results with placeholder

Based on OpenClaw's context-pruning pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.shared.logger import get_logger

from .token_counter import TokenCounter

logger = get_logger("lexicon.engine.context.pruner")

# Thresholds (fraction of total budget)
SOFT_TRIM_RATIO = 0.70   # Start soft-trimming at 70% usage
HARD_CLEAR_RATIO = 0.90  # Start hard-clearing at 90% usage

# Soft trim: keep this many chars from head and tail of large tool results
HEAD_CHARS = 500
TAIL_CHARS = 300
# Only trim tool results larger than this
MIN_TRIM_CHARS = 1500

# Hard clear placeholder
HARD_CLEAR_PLACEHOLDER = "[Tool output cleared to free context space]"


@dataclass
class PruneResult:
    """Result of a pruning operation."""
    messages: list[dict[str, Any]]
    soft_trimmed: int   # Number of messages soft-trimmed
    hard_cleared: int   # Number of messages hard-cleared
    tokens_before: int
    tokens_after: int

    @property
    def tokens_saved(self) -> int:
        return self.tokens_before - self.tokens_after


class ContextPruner:
    """Prunes conversation messages to fit within token budget.

    Only targets tool_result messages — the biggest token hogs.
    User messages and assistant text are never modified.

    Usage:
        pruner = ContextPruner(token_counter)
        result = pruner.prune(messages, budget_total=120000)
        # result.messages is the pruned list
    """

    def __init__(self, counter: TokenCounter):
        self._counter = counter

    def prune(
        self,
        messages: list[dict[str, Any]],
        budget_total: int,
    ) -> PruneResult:
        """Prune messages to fit within budget.

        Applies soft trim first, then hard clear if still over budget.
        Returns a new list — does NOT modify the input.

        Args:
            messages: Conversation message list
            budget_total: Total token budget for messages

        Returns:
            PruneResult with pruned messages and stats
        """
        tokens_before = self._counter.count_messages(messages)

        # Under soft trim threshold? No pruning needed.
        if tokens_before <= budget_total * SOFT_TRIM_RATIO:
            return PruneResult(
                messages=messages,
                soft_trimmed=0,
                hard_cleared=0,
                tokens_before=tokens_before,
                tokens_after=tokens_before,
            )

        # Copy messages (don't mutate input)
        pruned = [self._copy_message(m) for m in messages]
        soft_count = 0
        hard_count = 0

        # Stage 1: Soft trim — truncate large tool results
        if tokens_before > budget_total * SOFT_TRIM_RATIO:
            for i, msg in enumerate(pruned):
                if self._is_prunable_tool_result(msg):
                    trimmed = self._soft_trim_message(msg)
                    if trimmed is not msg:
                        pruned[i] = trimmed
                        soft_count += 1

            tokens_after_soft = self._counter.count_messages(pruned)
            logger.debug(
                f"Soft trim: {soft_count} messages, "
                f"{tokens_before} → {tokens_after_soft} tokens"
            )

            # Stage 2: Hard clear — if still over budget
            if tokens_after_soft > budget_total * HARD_CLEAR_RATIO:
                # Clear oldest prunable messages first
                for i, msg in enumerate(pruned):
                    if self._is_prunable_tool_result(msg):
                        cleared = self._hard_clear_message(msg)
                        if cleared is not msg:
                            pruned[i] = cleared
                            hard_count += 1

                        # Check if we're under budget now
                        current = self._counter.count_messages(pruned)
                        if current <= budget_total * HARD_CLEAR_RATIO:
                            break

        tokens_after = self._counter.count_messages(pruned)

        if soft_count > 0 or hard_count > 0:
            logger.info(
                f"Pruned: {soft_count} soft-trimmed, {hard_count} hard-cleared. "
                f"Tokens: {tokens_before} → {tokens_after} "
                f"(saved {tokens_before - tokens_after})"
            )

        return PruneResult(
            messages=pruned,
            soft_trimmed=soft_count,
            hard_cleared=hard_count,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
        )

    # ── Pruning Operations ────────────────────────────────────────

    def _soft_trim_message(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Soft trim: keep head + tail of large tool result content."""
        content = msg.get("content", "")

        if isinstance(content, str):
            if len(content) > MIN_TRIM_CHARS:
                trimmed = self._trim_text(content)
                return {**msg, "content": trimmed}

        elif isinstance(content, list):
            new_content = []
            changed = False
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    block_content = block.get("content", "")
                    if isinstance(block_content, str) and len(block_content) > MIN_TRIM_CHARS:
                        new_block = {**block, "content": self._trim_text(block_content)}
                        new_content.append(new_block)
                        changed = True
                        continue
                new_content.append(block)
            if changed:
                return {**msg, "content": new_content}

        return msg

    def _hard_clear_message(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Hard clear: replace tool result content with placeholder."""
        content = msg.get("content", "")

        if isinstance(content, str):
            return {**msg, "content": HARD_CLEAR_PLACEHOLDER}

        elif isinstance(content, list):
            new_content = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    new_content.append({
                        **block,
                        "content": HARD_CLEAR_PLACEHOLDER,
                    })
                else:
                    new_content.append(block)
            return {**msg, "content": new_content}

        return msg

    def _trim_text(self, text: str) -> str:
        """Keep head and tail, replace middle with ellipsis."""
        head = text[:HEAD_CHARS]
        tail = text[-TAIL_CHARS:]
        trimmed_chars = len(text) - HEAD_CHARS - TAIL_CHARS
        return f"{head}\n\n[...{trimmed_chars} chars trimmed...]\n\n{tail}"

    # ── Helpers ───────────────────────────────────────────────────

    def _is_prunable_tool_result(self, msg: dict[str, Any]) -> bool:
        """Check if a message is a tool result that can be pruned.

        Only prune tool_result messages from the "user" role
        (which is how Anthropic API formats tool results).
        Never prune actual user messages or assistant text.
        """
        if msg.get("role") != "user":
            return False

        content = msg.get("content")

        # Structured content with tool_result blocks
        if isinstance(content, list):
            return any(
                isinstance(b, dict) and b.get("type") == "tool_result"
                for b in content
            )

        return False

    def _copy_message(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Shallow copy a message dict."""
        return {**msg}
