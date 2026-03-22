"""RSS feed fetcher tool — fetch and parse RSS/Atom feeds.

Uses httpx + simple XML parsing (no feedparser dependency needed).
Returns the latest entries from a feed URL.
"""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree

import httpx

from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.tools.rss_fetch")

TOOL_DEF: dict[str, Any] = {
    "name": "rss_fetch",
    "description": (
        "Fetch the latest entries from an RSS or Atom feed. "
        "Returns titles, links, and summaries. "
        "Use this for monitoring blogs and news sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The RSS/Atom feed URL",
            },
            "max_entries": {
                "type": "integer",
                "description": "Maximum entries to return (default 5, max 20)",
                "default": 5,
            },
        },
        "required": ["url"],
    },
}

# Common AI/ML blog feeds (used by the web-researcher skill)
KNOWN_FEEDS: dict[str, str] = {
    "anthropic": "https://www.anthropic.com/feed.xml",
    "openai": "https://openai.com/blog/rss.xml",
    "simonwillison": "https://simonwillison.net/atom/everything/",
    "chiphuyen": "https://huyenchip.com/feed.xml",
    "lilianweng": "https://lilianweng.github.io/index.xml",
    "huggingface": "https://huggingface.co/blog/feed.xml",
}

# XML namespaces for Atom feeds
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_rss(root: ElementTree.Element) -> list[dict[str, str]]:
    """Parse RSS 2.0 feed."""
    entries = []
    for item in root.iter("item"):
        entry = {
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "summary": _clean_html(item.findtext("description") or ""),
            "published": (item.findtext("pubDate") or "").strip(),
        }
        entries.append(entry)
    return entries


def _parse_atom(root: ElementTree.Element) -> list[dict[str, str]]:
    """Parse Atom feed."""
    entries = []
    for entry in root.findall("atom:entry", ATOM_NS):
        link_el = entry.find("atom:link", ATOM_NS)
        link = link_el.get("href", "") if link_el is not None else ""

        summary_el = entry.find("atom:summary", ATOM_NS) or entry.find("atom:content", ATOM_NS)
        summary = _clean_html(summary_el.text or "") if summary_el is not None else ""

        entries.append({
            "title": (entry.findtext("atom:title", "", ATOM_NS) or "").strip(),
            "link": link,
            "summary": summary[:500],
            "published": (entry.findtext("atom:published", "", ATOM_NS)
                         or entry.findtext("atom:updated", "", ATOM_NS) or "").strip(),
        })
    return entries


async def rss_fetch(url: str, max_entries: int = 5) -> str:
    """Fetch and parse an RSS/Atom feed.

    Returns formatted entries with title, link, date, and summary.
    """
    max_entries = min(max_entries, 20)

    # Resolve known feed aliases
    if url.lower() in KNOWN_FEEDS:
        url = KNOWN_FEEDS[url.lower()]

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Lexicon.ai/1.0 (RSS Reader)"},
            )
            resp.raise_for_status()

        root = ElementTree.fromstring(resp.text)

        # Detect feed type and parse
        if root.tag == "rss" or root.find("channel") is not None:
            entries = _parse_rss(root)
        elif root.tag.endswith("feed") or root.find("atom:entry", ATOM_NS) is not None:
            entries = _parse_atom(root)
        else:
            return f"Unrecognized feed format at {url}"

        entries = entries[:max_entries]

        if not entries:
            return f"No entries found in feed: {url}"

        lines = [f"## Feed: {url}\n"]
        for i, e in enumerate(entries, 1):
            lines.append(f"**{i}. {e['title']}**")
            if e["link"]:
                lines.append(f"   Link: {e['link']}")
            if e["published"]:
                lines.append(f"   Date: {e['published']}")
            if e["summary"]:
                lines.append(f"   {e['summary'][:300]}")
            lines.append("")

        return "\n".join(lines)

    except httpx.HTTPStatusError as e:
        logger.error(f"RSS fetch HTTP error: {e.response.status_code} for {url}")
        return f"RSS fetch failed (HTTP {e.response.status_code}): {url}"
    except ElementTree.ParseError as e:
        logger.error(f"RSS parse error for {url}: {e}")
        return f"Failed to parse feed XML from {url}: {e}"
    except Exception as e:
        logger.error(f"RSS fetch failed for {url}: {e}")
        return f"RSS fetch failed: {e}"
