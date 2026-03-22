"""Hook registry — in-memory event bus with colon-separated naming.

Event naming convention:
    category:action           — two levels (most events)
    category:action:target    — three levels (tool hooks)

Registration matching uses prefix on colon segments:
    register("tool:after:vault_write")  → exact match only
    register("tool:after")              → matches any tool:after:*
    register("tool")                    → matches any tool:*:*

Handlers are async functions: async def handler(event: HookEvent) -> None
Errors in one handler don't block others (isolated execution).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine

from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.hooks.registry")

# Handler type: async function that takes a HookEvent
HookHandler = Callable[["HookEvent"], Coroutine[Any, Any, None]]


@dataclass
class HookEvent:
    """Event data passed to hook handlers."""
    name: str               # Full event name, e.g. "tool:after:vault_write"
    category: str           # First segment, e.g. "tool"
    action: str             # Second segment, e.g. "after"
    target: str             # Third segment (if any), e.g. "vault_write"
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def from_name(name: str, data: dict[str, Any] | None = None) -> "HookEvent":
        """Create a HookEvent from a colon-separated name."""
        parts = name.split(":")
        return HookEvent(
            name=name,
            category=parts[0] if len(parts) >= 1 else "",
            action=parts[1] if len(parts) >= 2 else "",
            target=parts[2] if len(parts) >= 3 else "",
            data=data or {},
        )


class HookRegistry:
    """Central event bus for the hook system.

    Usage:
        registry = HookRegistry()

        # Register handlers
        registry.register("meeting:stop", on_meeting_stop)
        registry.register("tool:after", log_all_tool_results)
        registry.register("tool", log_everything_tool_related)

        # Trigger an event — all matching handlers fire
        await registry.trigger("tool:after:vault_write", {"path": "..."})

        # Unregister
        registry.unregister("meeting:stop", on_meeting_stop)
    """

    def __init__(self) -> None:
        # pattern → [handlers]
        # Pattern is either exact or a prefix (e.g. "tool" matches "tool:after:x")
        self._handlers: dict[str, list[HookHandler]] = defaultdict(list)

    def register(self, pattern: str, handler: HookHandler) -> None:
        """Register a handler for an event pattern.

        Args:
            pattern: Event pattern to match. Can be:
                     "meeting:stop"            — exact match
                     "tool:after"              — prefix, matches tool:after:*
                     "tool"                    — prefix, matches tool:*:*
            handler: Async function(HookEvent) → None
        """
        if handler in self._handlers[pattern]:
            logger.warning(f"Handler already registered for '{pattern}', skipping")
            return
        self._handlers[pattern].append(handler)
        logger.debug(f"Hook registered: '{pattern}' → {handler.__name__}")

    def unregister(self, pattern: str, handler: HookHandler) -> bool:
        """Remove a specific handler from a pattern. Returns True if found."""
        handlers = self._handlers.get(pattern, [])
        if handler in handlers:
            handlers.remove(handler)
            if not handlers:
                del self._handlers[pattern]
            logger.debug(f"Hook unregistered: '{pattern}' → {handler.__name__}")
            return True
        return False

    def clear(self, pattern: str | None = None) -> None:
        """Clear handlers. If pattern given, clear only that pattern. Else clear all."""
        if pattern:
            self._handlers.pop(pattern, None)
        else:
            self._handlers.clear()

    async def trigger(
        self,
        event_name: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Fire an event — all matching handlers execute.

        Matching uses prefix on colon segments:
            trigger("tool:after:vault_write") fires handlers for:
            - "tool:after:vault_write"  (exact)
            - "tool:after"              (prefix)
            - "tool"                    (prefix)

        Handlers run concurrently. Errors are caught and logged —
        one failing handler doesn't block others.
        """
        event = HookEvent.from_name(event_name, data)
        handlers = self._resolve_handlers(event_name)

        if not handlers:
            return

        logger.debug(
            f"Hook trigger: '{event_name}' → {len(handlers)} handler(s)"
        )

        # Run all handlers concurrently, catch errors individually
        results = await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers),
            return_exceptions=True,
        )

        # Log any unexpected exceptions (handler errors already logged in _safe_call)
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Hook gather exception for '{event_name}': {r}")

    def _resolve_handlers(self, event_name: str) -> list[HookHandler]:
        """Find all handlers matching an event name via prefix matching.

        For event "tool:after:vault_write", matches patterns:
            "tool:after:vault_write"  — exact
            "tool:after"              — 2-segment prefix
            "tool"                    — 1-segment prefix

        Handlers are returned in order: broadest prefix first, exact last.
        """
        parts = event_name.split(":")
        handlers: list[HookHandler] = []

        # Check all prefix lengths: "tool", "tool:after", "tool:after:vault_write"
        for i in range(1, len(parts) + 1):
            prefix = ":".join(parts[:i])
            handlers.extend(self._handlers.get(prefix, []))

        return handlers

    async def _safe_call(self, handler: HookHandler, event: HookEvent) -> None:
        """Call a handler with error isolation."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"Hook handler '{handler.__name__}' failed "
                f"for event '{event.name}': {e}"
            )

    # ── Introspection ─────────────────────────────────────────────

    def list_patterns(self) -> list[str]:
        """List all registered patterns."""
        return list(self._handlers.keys())

    def handler_count(self, pattern: str | None = None) -> int:
        """Count handlers for a pattern, or total if no pattern given."""
        if pattern:
            return len(self._handlers.get(pattern, []))
        return sum(len(h) for h in self._handlers.values())


# ── Global Singleton ──────────────────────────────────────────────

_global_registry: HookRegistry | None = None


def get_registry() -> HookRegistry:
    """Get the global hook registry (singleton)."""
    global _global_registry
    if _global_registry is None:
        _global_registry = HookRegistry()
    return _global_registry


async def trigger_hook(event_name: str, data: dict[str, Any] | None = None) -> None:
    """Trigger a hook on the global registry. Convenience function."""
    await get_registry().trigger(event_name, data)


def register_hook(pattern: str, handler: HookHandler) -> None:
    """Register a hook on the global registry. Convenience function."""
    get_registry().register(pattern, handler)


def unregister_hook(pattern: str, handler: HookHandler) -> bool:
    """Unregister a hook from the global registry. Convenience function."""
    return get_registry().unregister(pattern, handler)
