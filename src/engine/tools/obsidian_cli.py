"""Obsidian CLI tool wrappers — search, read, write, move notes via obsidian-cli.

Uses obsidian-cli (brew install yakitrak/yakitrak/obsidian-cli) for vault operations.
Key advantage over direct file I/O: wiki-link-aware rename/move, fuzzy search.

All commands target the Lexicon vault via --vault flag.
"""

from __future__ import annotations

import asyncio
import shutil
from typing import Any

from src.shared.constants import VAULT_DIR
from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.tools.obsidian_cli")

# Vault name for obsidian-cli (derived from vault path)
_VAULT_NAME = VAULT_DIR.name if VAULT_DIR else "vault"

# Check if obsidian-cli is available
_CLI_PATH = shutil.which("obsidian-cli")


async def _run_cli(*args: str, timeout: float = 10.0) -> tuple[str, str, int]:
    """Run an obsidian-cli command and return (stdout, stderr, returncode)."""
    if not _CLI_PATH:
        return "", "obsidian-cli not installed. Run: brew install yakitrak/yakitrak/obsidian-cli", 1

    cmd = [_CLI_PATH, *args, "--vault", _VAULT_NAME]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (
            stdout.decode().strip(),
            stderr.decode().strip(),
            proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        return "", f"obsidian-cli timed out after {timeout}s", 1
    except Exception as e:
        return "", str(e), 1


# ── Tool: obsidian_search ──────────────────────────────────────

SEARCH_TOOL_DEF: dict[str, Any] = {
    "name": "obsidian_search",
    "description": (
        "Search note content in the Obsidian vault. Returns matching notes "
        "with their content. Use for finding terms, patterns, decisions, or "
        "any knowledge stored in the vault."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term to find in note content",
            },
        },
        "required": ["query"],
    },
}


async def obsidian_search(query: str) -> str:
    """Search vault note content for a term."""
    stdout, stderr, code = await _run_cli("search-content", query)
    if code != 0:
        logger.warning(f"obsidian search failed: {stderr}")
        return f"Search failed: {stderr}"
    if not stdout:
        return f"No notes found matching: {query}"
    return stdout


# ── Tool: obsidian_read ────────────────────────────────────────

READ_TOOL_DEF: dict[str, Any] = {
    "name": "obsidian_read",
    "description": (
        "Read the full content of a note from the Obsidian vault. "
        "Pass the note name (without .md extension). "
        "Use --mentions to include linked mentions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "description": "Note name or path (e.g. 'terms/saga-pattern')",
            },
            "include_mentions": {
                "type": "boolean",
                "description": "Include linked mentions from other notes",
                "default": False,
            },
        },
        "required": ["note"],
    },
}


async def obsidian_read(note: str, include_mentions: bool = False) -> str:
    """Read a note's content from the vault."""
    args = ["print", note]
    if include_mentions:
        args.append("--mentions")
    stdout, stderr, code = await _run_cli(*args)
    if code != 0:
        logger.warning(f"obsidian read failed: {stderr}")
        return f"Note not found: {note}"
    return stdout


# ── Tool: obsidian_create ──────────────────────────────────────

CREATE_TOOL_DEF: dict[str, Any] = {
    "name": "obsidian_create",
    "description": (
        "Create or update a note in the Obsidian vault. "
        "Pass the note path and content. Use append=true to add to existing note."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "description": "Note path (e.g. 'terms/saga-pattern')",
            },
            "content": {
                "type": "string",
                "description": "Markdown content for the note",
            },
            "append": {
                "type": "boolean",
                "description": "Append to existing note instead of overwriting",
                "default": False,
            },
        },
        "required": ["note", "content"],
    },
}


async def obsidian_create(note: str, content: str, append: bool = False) -> str:
    """Create or update a note in the vault."""
    args = ["create", note, "--content", content]
    if append:
        args.append("--append")
    else:
        args.append("--overwrite")
    stdout, stderr, code = await _run_cli(*args)
    if code != 0:
        logger.warning(f"obsidian create failed: {stderr}")
        return f"Failed to create note: {stderr}"
    return f"Note created: {note}"


# ── Tool: obsidian_move ────────────────────────────────────────

MOVE_TOOL_DEF: dict[str, Any] = {
    "name": "obsidian_move",
    "description": (
        "Move or rename a note in the Obsidian vault. "
        "Automatically updates all [[wiki-links]] across the vault."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Current note path",
            },
            "destination": {
                "type": "string",
                "description": "New note path",
            },
        },
        "required": ["source", "destination"],
    },
}


async def obsidian_move(source: str, destination: str) -> str:
    """Move/rename a note and update all wiki-links."""
    stdout, stderr, code = await _run_cli("move", source, destination)
    if code != 0:
        logger.warning(f"obsidian move failed: {stderr}")
        return f"Failed to move note: {stderr}"
    return f"Moved: {source} → {destination} (links updated)"


# ── Tool: obsidian_list ────────────────────────────────────────

LIST_TOOL_DEF: dict[str, Any] = {
    "name": "obsidian_list",
    "description": (
        "List files and folders in the Obsidian vault. "
        "Optionally pass a subdirectory path."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Subdirectory to list (e.g. 'terms', 'papers'). Empty for root.",
                "default": "",
            },
        },
    },
}


async def obsidian_list(path: str = "") -> str:
    """List files in the vault."""
    args = ["list"]
    if path:
        args.append(path)
    stdout, stderr, code = await _run_cli(*args)
    if code != 0:
        logger.warning(f"obsidian list failed: {stderr}")
        return f"Failed to list: {stderr}"
    return stdout or "Empty directory"
