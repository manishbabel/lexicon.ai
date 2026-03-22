"""Hook system — event bus for agent lifecycle.

Colon-separated event naming: category:action[:target]
Prefix matching: register("tool") catches all tool:* events.
"""

from .registry import HookRegistry, get_registry, register_hook, trigger_hook, unregister_hook

__all__ = [
    "HookRegistry",
    "get_registry",
    "register_hook",
    "trigger_hook",
    "unregister_hook",
]
