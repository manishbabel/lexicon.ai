"""Compactor — Stage 2: LLM-based summarization of old messages.

Runs AFTER pruning, when pruning alone isn't enough to fit the budget.
Summarizes chunks of old conversation into compact digests via LLM.
The summary replaces the original messages, preserving key facts/decisions.

Security: strips tool result details before sending to LLM for summarization
(tool results can contain untrusted/verbose payloads).

Based on OpenClaw's compaction pattern.
"""

from __future__ import annotations

from typing import Any

from src.shared.logger import get_logger

from ..llm.provider import LLMProvider
from .token_counter import TokenCounter

logger = get_logger("lexicon.engine.context.compactor")

# Compaction triggers when messages exceed this fraction of budget
COMPACTION_THRESHOLD = 0.85

# How many messages to keep at the tail (recent, never compacted)
PROTECTED_TAIL = 6

# How many messages to keep at the head (initial context, never compacted)
PROTECTED_HEAD = 2

# Max tokens for the compaction summary
SUMMARY_MAX_TOKENS = 1024

# Compaction system prompt
COMPACTION_PROMPT = """You are a conversation compactor. Summarize the following conversation chunk
into a concise digest that preserves:
1. Key decisions made
2. Important facts/data mentioned
3. Action items or commitments
4. Technical terms and patterns discussed
5. Any unresolved questions

Be concise but don't lose critical information. Use bullet points.
Do NOT include raw tool output or verbose data — only the conclusions drawn from tools.
Output ONLY the summary, no preamble."""


class Compactor:
    """LLM-based conversation compaction.

    Summarizes old messages into compact digests when the conversation
    exceeds the token budget. Preserves key facts, decisions, and context.

    Usage:
        compactor = Compactor(llm=provider, counter=token_counter)
        messages = await compactor.compact_if_needed(messages, budget=100000)
    """

    def __init__(self, llm: LLMProvider, counter: TokenCounter):
        self._llm = llm
        self._counter = counter

    async def compact_if_needed(
        self,
        messages: list[dict[str, Any]],
        budget: int,
    ) -> list[dict[str, Any]]:
        """Compact messages if they exceed the budget threshold.

        Returns compacted messages (or original if no compaction needed).
        Does NOT modify the input list.

        Args:
            messages: Conversation message list
            budget: Token budget for messages section

        Returns:
            Possibly-compacted message list
        """
        current_tokens = self._counter.count_messages(messages)

        if current_tokens <= budget * COMPACTION_THRESHOLD:
            return messages

        logger.info(
            f"Compaction triggered: {current_tokens} tokens "
            f"exceeds {COMPACTION_THRESHOLD * 100:.0f}% of {budget} budget"
        )

        return await self._compact(messages, budget)

    async def _compact(
        self,
        messages: list[dict[str, Any]],
        budget: int,
    ) -> list[dict[str, Any]]:
        """Perform the actual compaction.

        Strategy:
        1. Protect head (first N) and tail (last N) messages
        2. Take the middle chunk (candidates for compaction)
        3. Sanitize: strip tool result details
        4. Summarize via LLM
        5. Replace middle chunk with summary message
        """
        n = len(messages)

        # Nothing to compact if too few messages
        if n <= PROTECTED_HEAD + PROTECTED_TAIL:
            return messages

        head = messages[:PROTECTED_HEAD]
        tail = messages[-PROTECTED_TAIL:]
        middle = messages[PROTECTED_HEAD: n - PROTECTED_TAIL]

        if not middle:
            return messages

        # Sanitize middle messages (strip sensitive tool output)
        sanitized = self._sanitize_for_llm(middle)

        # Format as text for the LLM
        text_to_summarize = self._format_messages_as_text(sanitized)

        # Check if even the sanitized text is worth summarizing
        sanitized_tokens = self._counter.count(text_to_summarize)
        if sanitized_tokens < 100:
            return messages

        # Summarize via LLM
        try:
            summary = await self._generate_summary(text_to_summarize)
        except Exception as e:
            logger.error(f"Compaction LLM call failed: {e}")
            # Fallback: simple truncation (drop middle, keep head+tail)
            return self._fallback_compact(head, middle, tail)

        # Build the compacted message list
        summary_message = {
            "role": "user",
            "content": (
                "[COMPACTED CONVERSATION SUMMARY — "
                f"the following summarizes {len(middle)} earlier messages]\n\n"
                + summary
            ),
        }

        compacted = head + [summary_message] + tail

        tokens_after = self._counter.count_messages(compacted)
        logger.info(
            f"Compacted {len(middle)} messages into summary. "
            f"Tokens: {self._counter.count_messages(messages)} → {tokens_after}"
        )

        return compacted

    async def _generate_summary(self, text: str) -> str:
        """Call the LLM to summarize conversation text."""
        messages = [{"role": "user", "content": text}]

        full_text = ""
        async for event in self._llm.stream(
            system=COMPACTION_PROMPT,
            messages=messages,
            tools=None,
            model=self._counter.model,
            max_tokens=SUMMARY_MAX_TOKENS,
        ):
            if event.type == "text_delta":
                full_text += event.text
            elif event.type == "stop":
                break

        return full_text.strip()

    # ── Sanitization ──────────────────────────────────────────────

    def _sanitize_for_llm(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Strip tool result details before sending to LLM for summarization.

        Security: tool results can contain untrusted/verbose payloads.
        We only keep a brief note about what tool was called.
        """
        sanitized = []
        for msg in messages:
            content = msg.get("content")

            if isinstance(content, list):
                new_blocks = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            # Replace verbose tool result with brief note
                            tool_content = block.get("content", "")
                            brief = (
                                str(tool_content)[:200]
                                if tool_content
                                else "[no output]"
                            )
                            new_blocks.append({
                                **block,
                                "content": f"[Tool result: {brief}]",
                            })
                        elif block.get("type") == "tool_use":
                            # Keep tool use but truncate large inputs
                            tool_input = block.get("input", {})
                            brief_input = str(tool_input)[:200]
                            new_blocks.append({
                                **block,
                                "input": brief_input,
                            })
                        else:
                            new_blocks.append(block)
                    else:
                        new_blocks.append(block)
                sanitized.append({**msg, "content": new_blocks})
            else:
                sanitized.append(msg)

        return sanitized

    def _format_messages_as_text(
        self, messages: list[dict[str, Any]]
    ) -> str:
        """Format messages as readable text for the LLM summarizer."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if isinstance(content, str):
                lines.append(f"[{role}]: {content}")
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type", "")
                        if block_type == "tool_result":
                            parts.append(f"[tool_result: {block.get('content', '')[:200]}]")
                        elif block_type == "tool_use":
                            parts.append(f"[called {block.get('name', '?')}]")
                        else:
                            parts.append(str(block)[:200])
                    else:
                        parts.append(str(block)[:200])
                lines.append(f"[{role}]: {' | '.join(parts)}")

        return "\n".join(lines)

    # ── Fallback ──────────────────────────────────────────────────

    def _fallback_compact(
        self,
        head: list[dict[str, Any]],
        middle: list[dict[str, Any]],
        tail: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fallback when LLM summarization fails — simple drop with note."""
        note = {
            "role": "user",
            "content": (
                f"[CONTEXT NOTE: {len(middle)} earlier messages were removed "
                "to fit context budget. Key points may have been lost.]"
            ),
        }
        return head + [note] + tail
