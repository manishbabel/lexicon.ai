"""Vault collection management — creates dirs and registers with QMD."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

from src.shared.constants import QMD_COLLECTION, VAULT_DIR
from src.shared.logger import get_logger

logger = get_logger("lexicon.search.collections")

# Vault subdirectories and what they hold
VAULT_SUBDIRS: dict[str, str] = {
    "terms": "Concept definitions, glossary entries, and terminology notes",
    "papers": "Paper summaries, annotations, and reading notes",
    "insights": "Synthesized insights and cross-topic connections",
    "patterns": "Design patterns — architecture diagrams, trade-offs, when-to-use guides",
    "concepts": "Broader concepts and mental models extracted from papers and blogs",
    "curriculum": "Course structures, lesson plans, assignments, and teaching materials",
    "references": "Curated external references, screenshots, source notes, and inspiration",
    "assets": "Generated or collected media assets such as images, videos, logos, and diagrams",
    "transcripts": "Meeting transcripts and conversation logs",
    "daily": "Daily notes and working journal",
    "archive": "Retired or superseded notes",
}


def ensure_vault_dirs() -> Path:
    """Create the vault root and all subdirectories if they don't exist.

    Returns:
        The vault root path.
    """
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in VAULT_SUBDIRS:
        (VAULT_DIR / subdir).mkdir(exist_ok=True)
    logger.info(f"Vault directories ensured at {VAULT_DIR}")
    return VAULT_DIR


async def setup_collection(vault_path: Path | None = None) -> bool:
    """Register the vault as a QMD collection.

    Runs: qmd collection add <path> --name lexicon

    Args:
        vault_path: Override vault location. Defaults to VAULT_DIR.

    Returns:
        True if successful.
    """
    vault = vault_path or VAULT_DIR
    ensure_vault_dirs()

    qmd_bin = shutil.which("qmd")
    if not qmd_bin:
        logger.error("QMD binary not found in PATH.")
        return False

    cmd = [qmd_bin, "collection", "add", str(vault), "--name", QMD_COLLECTION]
    env = {**os.environ, "NO_COLOR": "1"}

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error = stderr.decode().strip()
        logger.error(f"Collection setup failed: {error}")
        return False

    logger.info(f"Collection '{QMD_COLLECTION}' registered at {vault}")
    return True


async def reindex() -> bool:
    """Trigger QMD to re-index the lexicon collection.

    Runs: qmd update

    Returns:
        True if successful.
    """
    qmd_bin = shutil.which("qmd")
    if not qmd_bin:
        logger.error("QMD binary not found in PATH.")
        return False

    cmd = [qmd_bin, "update"]
    env = {**os.environ, "NO_COLOR": "1"}

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error = stderr.decode().strip()
        logger.error(f"Reindex failed: {error}")
        return False

    logger.info("Reindex complete.")
    return True
