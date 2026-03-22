"""Load agent workspace files (AGENT.md, SOUL.md, IDENTITY.md)."""

from __future__ import annotations

from pathlib import Path

from src.shared.logger import get_logger
from src.shared.types import WorkspaceContext

logger = get_logger("lexicon.engine.workspace")

WORKSPACE_FILES = ["IDENTITY.md", "SOUL.md", "AGENT.md"]


def load_workspace(workspace_path: str | Path) -> WorkspaceContext:
    """Load all workspace markdown files from a directory.

    Reads:
      - IDENTITY.md → who the agent is (name, role, characteristics)
      - SOUL.md → personality, communication style
      - AGENT.md → behavioral instructions, rules

    Returns a WorkspaceContext with the content of each file.
    """
    path = Path(workspace_path)
    if not path.is_dir():
        logger.warning(f"Workspace directory not found: {path}")
        return WorkspaceContext()

    context = WorkspaceContext()

    identity_path = path / "IDENTITY.md"
    if identity_path.exists():
        context.identity = identity_path.read_text().strip()
        logger.debug(f"Loaded IDENTITY.md ({len(context.identity)} chars)")

    soul_path = path / "SOUL.md"
    if soul_path.exists():
        context.soul = soul_path.read_text().strip()
        logger.debug(f"Loaded SOUL.md ({len(context.soul)} chars)")

    agent_path = path / "AGENT.md"
    if agent_path.exists():
        context.agent = agent_path.read_text().strip()
        logger.debug(f"Loaded AGENT.md ({len(context.agent)} chars)")

    logger.info(f"Loaded workspace from {path}")
    return context


def build_system_prompt(
    workspace: WorkspaceContext,
    skills: list[str] | None = None,
    memory_context: str | None = None,
) -> str:
    """Build the full system prompt from workspace + skills + memory context.

    Combines all parts with clear section separators.
    """
    parts: list[str] = []

    if workspace.identity:
        parts.append(f"# Identity\n{workspace.identity}")

    if workspace.soul:
        parts.append(f"# Personality\n{workspace.soul}")

    if workspace.agent:
        parts.append(f"# Instructions\n{workspace.agent}")

    if skills:
        for skill_text in skills:
            parts.append(skill_text)

    if memory_context:
        parts.append(f"# Relevant Knowledge\n{memory_context}")

    return "\n\n---\n\n".join(parts)
