"""Skill registry — scan, index, match, hot-reload.

Skills are folders containing a SKILL.md file with YAML frontmatter.
The registry extracts lightweight metadata (name, description, triggers)
for the system prompt. Full SKILL.md content is loaded on demand via
AgentRuntime's read_skill tool.

Three-tier precedence (highest wins for same skill name):
  Tier 3 (highest): ~/.lexicon/workspaces/<persona>/skills/
  Tier 2 (middle):  ~/.lexicon/skills/
  Tier 1 (lowest):  workspaces/<persona>/skills/  (bundled in repo)

Hot-reload: watchfiles monitors all skill directories and re-indexes
when a SKILL.md is added, modified, or removed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from src.shared.constants import (
    BUNDLED_WORKSPACES,
    SKILLS_DIR,
    SKILL_WATCH_DEBOUNCE_MS,
    WORKSPACES_DIR,
)
from src.shared.frontmatter import parse_frontmatter
from src.shared.logger import get_logger
from src.shared.types import SkillDefinition, SkillTriggers

logger = get_logger("lexicon.engine.skills")


# ── Skill Metadata (lightweight, goes into system prompt) ────────

def _parse_skill_dir(skill_dir: Path, source: str) -> SkillDefinition | None:
    """Parse a single skill directory and extract metadata from SKILL.md.

    Returns None if SKILL.md is missing or unparseable.
    """
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return None

    try:
        meta, body = parse_frontmatter(skill_file)
    except Exception as e:
        logger.warning(f"Failed to parse {skill_file}: {e}")
        return None

    name = meta.get("name", skill_dir.name)
    description = meta.get("description", "")

    # Parse triggers from frontmatter
    raw_triggers = meta.get("triggers", {})
    if isinstance(raw_triggers, dict):
        triggers = SkillTriggers(
            keywords=raw_triggers.get("keywords", []),
            contexts=raw_triggers.get("contexts", []),
        )
    else:
        triggers = SkillTriggers()

    return SkillDefinition(
        name=name,
        description=description,
        triggers=triggers,
        instructions=body.strip(),
        base_dir=str(skill_dir),
        source=source,
    )


def _scan_skills_dir(parent: Path, source: str) -> list[SkillDefinition]:
    """Scan a directory for skill subdirectories (each containing SKILL.md)."""
    if not parent.exists() or not parent.is_dir():
        return []

    skills: list[SkillDefinition] = []
    for child in sorted(parent.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            skill = _parse_skill_dir(child, source)
            if skill:
                skills.append(skill)

    return skills


# ── Skill Registry ───────────────────────────────────────────────


class SkillRegistry:
    """Manages skill metadata with 3-tier precedence and hot-reload.

    Usage:
        registry = SkillRegistry()
        registry.load_all("software-engineer")
        metadata = registry.get_metadata()  # for system prompt
        matched = registry.match_triggers("let's discuss event sourcing")
    """

    def __init__(self) -> None:
        # Indexed by skill name → SkillDefinition (highest-precedence wins)
        self._skills: dict[str, SkillDefinition] = {}
        self._persona: str = ""
        self._watcher_task: asyncio.Task | None = None

    # ── Load ─────────────────────────────────────────────────────

    def load_all(self, persona: str) -> None:
        """Scan all 3 tiers and build the skill index.

        Tiers are loaded lowest-first so higher tiers overwrite by name.
        """
        self._persona = persona
        self._skills.clear()

        tiers: list[tuple[Path, str]] = [
            # Tier 1 (lowest): bundled with repo
            (BUNDLED_WORKSPACES / persona / "skills", "bundled"),
            # Tier 2 (middle): user's shared skills
            (SKILLS_DIR, "shared"),
            # Tier 3 (highest): user's workspace overrides
            (WORKSPACES_DIR / persona / "skills", "workspace"),
        ]

        for skills_path, source in tiers:
            for skill in _scan_skills_dir(skills_path, source):
                if skill.name in self._skills:
                    prev = self._skills[skill.name]
                    logger.debug(
                        f"Skill '{skill.name}' overridden: "
                        f"{prev.source} → {source}"
                    )
                self._skills[skill.name] = skill

        logger.info(
            f"Loaded {len(self._skills)} skills for '{persona}': "
            f"{list(self._skills.keys())}"
        )

    def reload(self) -> None:
        """Re-scan all tiers. Called on hot-reload."""
        if self._persona:
            self.load_all(self._persona)

    # ── Query ────────────────────────────────────────────────────

    def get_metadata(self) -> list[dict[str, str]]:
        """Return lightweight metadata for the system prompt.

        Format: [{name, description, path}] — this is what
        AgentRuntime.set_skill_metadata() expects.
        """
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "path": str(Path(skill.base_dir) / "SKILL.md"),
            }
            for skill in self._skills.values()
        ]

    def get_skill(self, name: str) -> SkillDefinition | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """List all skill names."""
        return list(self._skills.keys())

    def match_triggers(self, text: str) -> list[SkillDefinition]:
        """Return skills whose trigger keywords appear in the text.

        This is a cheap pre-filter — the LLM makes the final decision
        on which skills to actually use.

        Skills with no keywords match everything (always available).
        """
        text_lower = text.lower()
        matched: list[SkillDefinition] = []

        for skill in self._skills.values():
            keywords = skill.triggers.keywords
            if not keywords:
                # No keywords = always available
                matched.append(skill)
                continue

            for kw in keywords:
                if kw.lower() in text_lower:
                    matched.append(skill)
                    break

        return matched

    def match_contexts(self, context: str) -> list[SkillDefinition]:
        """Return skills whose trigger contexts match.

        Contexts are broader categories like "architecture",
        "code-review", "interview". Less granular than keywords.
        """
        context_lower = context.lower()
        matched: list[SkillDefinition] = []

        for skill in self._skills.values():
            contexts = skill.triggers.contexts
            if not contexts:
                continue
            for ctx in contexts:
                if ctx.lower() in context_lower:
                    matched.append(skill)
                    break

        return matched

    # ── Hot-Reload ───────────────────────────────────────────────

    async def start_watcher(self) -> None:
        """Start watching skill directories for changes.

        Uses watchfiles for efficient filesystem monitoring.
        Debounces rapid changes (e.g., editor save + format).
        """
        if self._watcher_task and not self._watcher_task.done():
            return

        self._watcher_task = asyncio.create_task(self._watch_loop())
        logger.info("Skill hot-reload watcher started")

    async def stop_watcher(self) -> None:
        """Stop the file watcher."""
        if self._watcher_task and not self._watcher_task.done():
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
        self._watcher_task = None
        logger.info("Skill hot-reload watcher stopped")

    async def _watch_loop(self) -> None:
        """Watch skill directories and reload on changes."""
        try:
            from watchfiles import awatch, Change
        except ImportError:
            logger.warning(
                "watchfiles not installed — skill hot-reload disabled. "
                "Install with: uv add watchfiles"
            )
            return

        # Collect all directories to watch
        watch_paths: list[Path] = []
        if self._persona:
            bundled = BUNDLED_WORKSPACES / self._persona / "skills"
            if bundled.exists():
                watch_paths.append(bundled)

            user_ws = WORKSPACES_DIR / self._persona / "skills"
            if user_ws.exists():
                watch_paths.append(user_ws)

        if SKILLS_DIR.exists():
            watch_paths.append(SKILLS_DIR)

        if not watch_paths:
            logger.debug("No skill directories to watch")
            return

        logger.debug(f"Watching skill dirs: {watch_paths}")

        debounce_ms = SKILL_WATCH_DEBOUNCE_MS

        try:
            async for changes in awatch(
                *watch_paths,
                debounce=debounce_ms,
                recursive=True,
            ):
                # Only reload if SKILL.md files were changed
                skill_changed = any(
                    Path(path).name == "SKILL.md"
                    for _change_type, path in changes
                )
                if skill_changed:
                    changed_files = [
                        Path(p).name
                        for _ct, p in changes
                        if Path(p).name == "SKILL.md"
                    ]
                    logger.info(
                        f"Skill files changed: {changed_files} — reloading"
                    )
                    self.reload()

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Skill watcher error: {e}")
