"""Paper fetch tool — fetch arxiv paper content for the agent.

Fetches the abstract page from arxiv and extracts structured info.
Uses the arxiv API for clean metadata and abstract text.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.tools.paper_fetch")

# Arxiv API endpoint
ARXIV_API_URL = "https://export.arxiv.org/api/query"

# Regex to extract arxiv ID from various URL formats
ARXIV_ID_PATTERN = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf|html)/|arxiv:)"
    r"(\d{4}\.\d{4,5}(?:v\d+)?)"
)


def _extract_arxiv_id(url_or_id: str) -> str | None:
    """Extract arxiv paper ID from a URL or raw ID."""
    # Already a bare ID like "2401.12345"
    if re.match(r"^\d{4}\.\d{4,5}(?:v\d+)?$", url_or_id.strip()):
        return url_or_id.strip()

    match = ARXIV_ID_PATTERN.search(url_or_id)
    return match.group(1) if match else None


def _clean_xml_text(text: str) -> str:
    """Remove XML tags and clean up whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_arxiv_entry(xml_text: str) -> dict[str, Any]:
    """Parse a single arxiv API entry from XML."""
    def _get(tag: str) -> str:
        match = re.search(f"<{tag}[^>]*>(.*?)</{tag}>", xml_text, re.DOTALL)
        return _clean_xml_text(match.group(1)) if match else ""

    def _get_all(tag: str) -> list[str]:
        return [_clean_xml_text(m) for m in re.findall(f"<{tag}[^>]*>(.*?)</{tag}>", xml_text, re.DOTALL)]

    # Extract authors (nested in <author><name>...</name></author>)
    authors = re.findall(r"<author>\s*<name>(.*?)</name>", xml_text)
    authors = [_clean_xml_text(a) for a in authors]

    # Extract categories
    categories = re.findall(r'<category[^>]*term="([^"]+)"', xml_text)

    # Extract links
    pdf_match = re.search(r'<link[^>]*title="pdf"[^>]*href="([^"]+)"', xml_text)
    pdf_url = pdf_match.group(1) if pdf_match else ""

    return {
        "title": _get("title"),
        "abstract": _get("summary"),
        "authors": authors,
        "categories": categories,
        "published": _get("published"),
        "updated": _get("updated"),
        "pdf_url": pdf_url,
    }


async def paper_fetch(url: str) -> str:
    """Fetch an arxiv paper's metadata and abstract.

    Args:
        url: Arxiv URL (abs, pdf, or html) or bare paper ID (e.g. "2401.12345").

    Returns:
        Formatted string with paper title, authors, abstract, categories, and URL.
    """
    arxiv_id = _extract_arxiv_id(url)
    if not arxiv_id:
        return f"Could not extract arxiv ID from: {url}"

    logger.info(f"Fetching arxiv paper: {arxiv_id}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                ARXIV_API_URL,
                params={"id_list": arxiv_id},
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"Failed to fetch paper {arxiv_id}: {e}"

    xml = resp.text

    # Check if paper was found
    if "<entry>" not in xml:
        return f"Paper not found on arxiv: {arxiv_id}"

    # Extract the entry
    entry_match = re.search(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    if not entry_match:
        return f"Could not parse arxiv response for: {arxiv_id}"

    paper = _parse_arxiv_entry(entry_match.group(1))

    # Format output for the agent
    lines = [
        f"# {paper['title']}",
        "",
        f"**Authors:** {', '.join(paper['authors'])}",
        f"**Published:** {paper['published'][:10]}",
        f"**Categories:** {', '.join(paper['categories'])}",
        f"**URL:** https://arxiv.org/abs/{arxiv_id}",
        f"**PDF:** {paper['pdf_url']}",
        "",
        "## Abstract",
        paper["abstract"],
    ]

    return "\n".join(lines)


# Tool definition for the registry
TOOL_DEF = {
    "name": "paper_fetch",
    "description": (
        "Fetch an arxiv paper's metadata and abstract. "
        "Pass an arxiv URL (e.g. https://arxiv.org/abs/2401.12345) or bare paper ID. "
        "Returns title, authors, abstract, categories, and links."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Arxiv URL or paper ID (e.g. '2401.12345')",
            },
        },
        "required": ["url"],
    },
}
