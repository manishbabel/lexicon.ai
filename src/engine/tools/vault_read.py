"""Vault read tool — agent tool wrapper around vault.reader.

Allows the agent to read specific vault files or list files by category.
"""

from __future__ import annotations

import json
from typing import Any

from src.shared.logger import get_logger
from src.vault.reader import list_files, read_file

logger = get_logger("lexicon.engine.tools.vault_read")


async def vault_read(path: str) -> str:
    """Read a specific file from the vault.

    Args:
        path: Relative path within vault (e.g. "terms/rag.md") or absolute path.

    Returns:
        File content with metadata, or error message.
    """
    result = read_file(path)

    if "error" in result:
        return f"Error: {result['error']} ({result['path']})"

    metadata = result["metadata"]
    body = result["body"]

    lines = [f"**File:** {result['path']}"]
    if metadata:
        lines.append(f"**Metadata:** {json.dumps(metadata, default=str)}")
    lines.append("")
    lines.append(body)

    return "\n".join(lines)


# Tool definition for the registry
TOOL_DEF = {
    "name": "vault_read",
    "description": (
        "Read a specific file from the Obsidian vault. "
        "Pass a relative path like 'terms/rag.md' or 'papers/2026-03-18-some-paper.md'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path within the vault (e.g. 'terms/rag.md')",
            },
        },
        "required": ["path"],
    },
}
