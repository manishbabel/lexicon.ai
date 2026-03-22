"""QMD search tool — agent tool wrapper around search.qmd_client.

Allows the agent to search the vault via QMD hybrid search.
Used for duplicate detection and finding related knowledge.
"""

from __future__ import annotations

import json
from typing import Any

from src.search.qmd_client import QMDClient
from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.tools.qmd_search")

# Module-level client (reused across calls)
_client: QMDClient | None = None


def _get_client() -> QMDClient:
    """Get or create the QMD client singleton."""
    global _client
    if _client is None:
        _client = QMDClient()
    return _client


async def qmd_search(query: str, n: int = 5) -> str:
    """Search the vault knowledge base via QMD hybrid search.

    Args:
        query: Search query text.
        n: Number of results to return (default 5).

    Returns:
        Formatted search results or "no results" message.
    """
    client = _get_client()

    if not client.available:
        return "QMD is not installed. Cannot search the vault. Install QMD and try again."

    results = await client.query(query, n=n)

    if not results:
        return f"No results found for: {query}"

    lines = [f"Found {len(results)} results for '{query}':", ""]
    for i, r in enumerate(results, 1):
        path = r.get("path", "unknown")
        score = r.get("score", 0.0)
        content = r.get("content", "")
        # Truncate content preview
        preview = content[:300] + "..." if len(content) > 300 else content
        lines.append(f"**{i}. {path}** (score: {score:.3f})")
        lines.append(preview)
        lines.append("")

    return "\n".join(lines)


# Tool definition for the registry
TOOL_DEF = {
    "name": "qmd_search",
    "description": (
        "Search the Obsidian vault knowledge base using QMD hybrid search "
        "(BM25 + vector + LLM rerank). Use this to find existing terms, papers, "
        "and insights. Always search before creating a new term to avoid duplicates."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query text",
            },
            "n": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}
