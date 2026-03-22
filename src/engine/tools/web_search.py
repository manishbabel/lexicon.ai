"""Web search tool — Tavily (primary) + DuckDuckGo (fallback).

Tavily returns clean, pre-extracted content ideal for AI agents.
DuckDuckGo is the free fallback when no Tavily key is configured.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.shared.config import get_settings
from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.tools.web_search")

TOOL_DEF: dict[str, Any] = {
    "name": "web_search",
    "description": (
        "Search the web for information. Returns extracted content from top results — "
        "not just links, but the actual text. Use for facts, benchmarks, pricing, "
        "documentation, or verifying claims made in the meeting."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default 3, max 5)",
                "default": 3,
            },
        },
        "required": ["query"],
    },
}

# ── Tavily (primary) ────────────────────────────────────────────

TAVILY_API_URL = "https://api.tavily.com/search"


async def _tavily_search(query: str, max_results: int, api_key: str) -> str | None:
    """Search via Tavily API. Returns formatted results or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                TAVILY_API_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": True,
                    "include_raw_content": False,
                    "search_depth": "basic",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        lines: list[str] = []

        # Tavily can return a direct answer
        answer = data.get("answer")
        if answer:
            lines.append(f"**Answer:** {answer}\n")

        # Individual results with extracted content
        results = data.get("results", [])
        if not results and not answer:
            return None

        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            content = r.get("content", "")
            lines.append(f"**{i}. {title}**")
            lines.append(f"   Source: {url}")
            if content:
                # Tavily returns pre-extracted content — truncate for context budget
                lines.append(f"   {content[:500]}")
            lines.append("")

        return "\n".join(lines) if lines else None

    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
        return None


# ── DuckDuckGo (fallback) ──────────────────────────────────────


async def _ddg_search(query: str, max_results: int) -> str:
    """Search via DuckDuckGo. Free, no API key needed."""
    # Try duckduckgo-search library first
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)

        if not results:
            return f"No results found for: {query}"

        lines: list[str] = []
        for i, r in enumerate(results, 1):
            lines.append(f"**{i}. {r.get('title', 'Untitled')}**")
            lines.append(f"   URL: {r.get('href', '')}")
            lines.append(f"   {r.get('body', '')}")
            lines.append("")

        return "\n".join(lines)

    except ImportError:
        pass

    # Fallback: scrape DuckDuckGo HTML
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; Lexicon.ai)"},
            )
            resp.raise_for_status()

        import re
        from urllib.parse import unquote

        links = re.findall(
            r'class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>',
            resp.text,
        )
        snippets = re.findall(
            r'class="result__snippet"[^>]*>([^<]*)</a>',
            resp.text,
        )

        lines: list[str] = []
        for i, (url, title) in enumerate(links[:max_results], 1):
            snippet = snippets[i - 1] if i - 1 < len(snippets) else ""
            actual_url = url
            if "uddg=" in url:
                match = re.search(r"uddg=([^&]+)", url)
                if match:
                    actual_url = unquote(match.group(1))

            lines.append(f"**{i}. {title.strip()}**")
            lines.append(f"   URL: {actual_url}")
            lines.append(f"   {snippet.strip()}")
            lines.append("")

        return "\n".join(lines) if lines else f"No results found for: {query}"

    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return f"Web search failed: {e}"


# ── Public API ─────────────────────────────────────────────────


async def web_search(query: str, max_results: int = 3) -> str:
    """Search the web. Uses Tavily if configured, falls back to DuckDuckGo."""
    max_results = min(max_results, 5)

    # Try Tavily first (better results, pre-extracted content)
    settings = get_settings()
    tavily_key = getattr(settings, "tavily_api_key", "") or ""
    if tavily_key:
        result = await _tavily_search(query, max_results, tavily_key)
        if result:
            logger.debug(f"Tavily search: {query}")
            return f"## Web Search: {query}\n\n{result}"

    # Fallback to DuckDuckGo
    logger.debug(f"DuckDuckGo fallback: {query}")
    ddg_result = await _ddg_search(query, max_results)
    return f"## Web Search: {query}\n\n{ddg_result}"
