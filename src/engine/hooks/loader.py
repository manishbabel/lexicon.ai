"""Hook loader — discover and load hooks from HOOK.md files on disk.

Hooks can be defined in the filesystem using HOOK.md files with
YAML frontmatter specifying which events to handle:

    workspaces/<persona>/hooks/<hook-name>/HOOK.md
    ~/.lexicon/hooks/<hook-name>/HOOK.md

HOOK.md frontmatter:
    ---
    name: my-hook
    events: ["meeting:stop", "agent:done"]
    description: Does something useful
    ---

    # Instructions for this hook
    (markdown body — used as context if the hook triggers an agent run)

For now, HOOK.md files define DECLARATIVE hooks that enqueue agent runs
with the hook's instructions as context. For custom Python logic,
register handlers in builtin.py instead.

This file is the foundation — user-defined hooks are a future feature.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.shared.constants import BUNDLED_WORKSPACES, LEXICON_HOME
from src.shared.frontmatter import parse_frontmatter
from src.shared.logger import get_logger

from .registry import HookEvent, get_registry

logger = get_logger("lexicon.engine.hooks.loader")


class HookDefinition:
    """A hook loaded from a HOOK.md file."""

    def __init__(
        self,
        name: str,
        events: list[str],
        description: str,
        instructions: str,
        base_dir: str,
    ):
        self.name = name
        self.events = events
        self.description = description
        self.instructions = instructions
        self.base_dir = base_dir

    async def handle(self, event: HookEvent) -> None:
        """Default handler: log the event.

        Subclass or extend this to enqueue agent runs with self.instructions
        as context. For now, just logs.
        """
        logger.info(
            f"HOOK.md '{self.name}' fired for event '{event.name}'"
        )


def _parse_hook_dir(hook_dir: Path) -> HookDefinition | None:
    """Parse a hook directory containing HOOK.md."""
    hook_file = hook_dir / "HOOK.md"
    if not hook_file.exists():
        return None

    try:
        meta, body = parse_frontmatter(hook_file)
    except Exception as e:
        logger.warning(f"Failed to parse {hook_file}: {e}")
        return None

    name = meta.get("name", hook_dir.name)
    events = meta.get("events", [])
    if isinstance(events, str):
        events = [events]

    if not events:
        logger.warning(f"Hook '{name}' has no events defined, skipping")
        return None

    return HookDefinition(
        name=name,
        events=events,
        description=meta.get("description", ""),
        instructions=body.strip(),
        base_dir=str(hook_dir),
    )


def _scan_hooks_dir(parent: Path) -> list[HookDefinition]:
    """Scan a directory for hook subdirectories."""
    if not parent.exists() or not parent.is_dir():
        return []

    hooks = []
    for child in sorted(parent.iterdir()):
        if child.is_dir() and (child / "HOOK.md").exists():
            hook = _parse_hook_dir(child)
            if hook:
                hooks.append(hook)
    return hooks


def load_filesystem_hooks(persona: str | None = None) -> list[HookDefinition]:
    """Load all HOOK.md hooks from disk and register them.

    Scans:
        1. Bundled: workspaces/<persona>/hooks/ (if persona given)
        2. User: ~/.lexicon/hooks/

    Returns list of loaded hook definitions.
    """
    registry = get_registry()
    loaded: list[HookDefinition] = []

    scan_dirs: list[Path] = []

    # Bundled hooks per persona
    if persona:
        scan_dirs.append(BUNDLED_WORKSPACES / persona / "hooks")

    # User-defined hooks
    scan_dirs.append(LEXICON_HOME / "hooks")

    for scan_dir in scan_dirs:
        for hook_def in _scan_hooks_dir(scan_dir):
            for event_pattern in hook_def.events:
                registry.register(event_pattern, hook_def.handle)
            loaded.append(hook_def)
            logger.info(
                f"Loaded filesystem hook '{hook_def.name}' "
                f"for events: {hook_def.events}"
            )

    if loaded:
        logger.info(f"Loaded {len(loaded)} filesystem hooks")

    return loaded
