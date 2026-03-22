"""Summarize CLI tool wrapper — summarize URLs, YouTube videos, PDFs, and local files.

Uses the `summarize` CLI (brew install steipete/tap/summarize) for content extraction
and summarization. Can also extract raw content without LLM summarization.

This complements web_search (Tavily): search finds the right URL,
summarize extracts and condenses the full page content.
"""

from __future__ import annotations

import asyncio
import shutil
from typing import Any

from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.tools.summarize_cli")

_CLI_PATH = shutil.which("summarize")

TOOL_DEF: dict[str, Any] = {
    "name": "summarize_url",
    "description": (
        "Summarize a URL, YouTube video, podcast, PDF, or local file. "
        "Returns a concise summary of the content. Use --extract to get "
        "raw content without LLM summarization. Good for reading articles, "
        "documentation pages, or YouTube transcripts."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "URL, YouTube link, or local file path to summarize",
            },
            "length": {
                "type": "string",
                "enum": ["short", "medium", "long"],
                "description": "Summary length (default: short for meetings)",
                "default": "short",
            },
            "extract_only": {
                "type": "boolean",
                "description": "Extract raw content without summarizing (faster, no LLM cost)",
                "default": False,
            },
            "style": {
                "type": "string",
                "enum": ["executive", "technical", "casual"],
                "description": "Summary style (default: technical)",
                "default": "technical",
            },
        },
        "required": ["source"],
    },
}


async def summarize_url(
    source: str,
    length: str = "short",
    extract_only: bool = False,
    style: str = "technical",
) -> str:
    """Summarize a URL or file using the summarize CLI."""
    if not _CLI_PATH:
        return "summarize CLI not installed. Run: brew install steipete/tap/summarize"

    args = [_CLI_PATH, source, "--length", length, "--style", style]
    if extract_only:
        args.append("--extract")

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

        if proc.returncode != 0:
            err = stderr.decode().strip()
            logger.warning(f"summarize failed: {err}")
            return f"Failed to summarize {source}: {err}"

        result = stdout.decode().strip()
        if not result:
            return f"No content extracted from: {source}"

        # Truncate for context budget
        if len(result) > 3000:
            result = result[:3000] + "\n\n...(truncated)"

        return result

    except asyncio.TimeoutError:
        return f"Summarize timed out for: {source} (30s limit)"
    except Exception as e:
        logger.error(f"summarize error: {e}")
        return f"Summarize failed: {e}"
