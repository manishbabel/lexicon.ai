"""Blogwatcher CLI tool wrapper — track blogs, scan for new articles.

Uses blogwatcher (go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest)
for persistent blog tracking with read/unread state in SQLite.

Key advantage over rss_fetch: knows what you've already seen, only surfaces new articles.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Any

from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.tools.blogwatcher_cli")

# blogwatcher installs to ~/go/bin/
_CLI_PATH = shutil.which("blogwatcher") or os.path.expanduser("~/go/bin/blogwatcher")


async def _run_cli(*args: str, timeout: float = 30.0) -> tuple[str, str, int]:
    """Run a blogwatcher command and return (stdout, stderr, returncode)."""
    if not os.path.exists(_CLI_PATH):
        return "", "blogwatcher not installed. Run: go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest", 1

    try:
        proc = await asyncio.create_subprocess_exec(
            _CLI_PATH, *args,
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
        return "", f"blogwatcher timed out after {timeout}s", 1
    except Exception as e:
        return "", str(e), 1


# ── Tool: blog_scan ────────────────────────────────────────────

SCAN_TOOL_DEF: dict[str, Any] = {
    "name": "blog_scan",
    "description": (
        "Scan all tracked blogs for new articles. Returns only NEW unread articles "
        "since the last scan. Use this for the daily blog scan cron job."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}


async def blog_scan() -> str:
    """Scan all tracked blogs for new articles."""
    stdout, stderr, code = await _run_cli("scan")
    if code != 0:
        return f"Blog scan failed: {stderr}"

    # Now get unread articles
    articles_out, articles_err, articles_code = await _run_cli("articles")
    if articles_code != 0:
        return f"Scan completed but failed to list articles: {articles_err}"

    if not articles_out:
        return "No new articles found."
    return f"## New Articles\n\n{articles_out}"


# ── Tool: blog_add ─────────────────────────────────────────────

ADD_TOOL_DEF: dict[str, Any] = {
    "name": "blog_add",
    "description": (
        "Add a blog to track. Auto-discovers RSS/Atom feed from the URL. "
        "Once added, blog_scan will detect new articles from this blog."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Short name for the blog (e.g. 'simon-willison')",
            },
            "url": {
                "type": "string",
                "description": "Blog URL (e.g. 'https://simonwillison.net')",
            },
        },
        "required": ["name", "url"],
    },
}


async def blog_add(name: str, url: str) -> str:
    """Add a blog to track."""
    stdout, stderr, code = await _run_cli("add", name, url)
    if code != 0:
        return f"Failed to add blog: {stderr}"
    return stdout or f"Added blog: {name} ({url})"


# ── Tool: blog_list ────────────────────────────────────────────

LIST_TOOL_DEF: dict[str, Any] = {
    "name": "blog_list",
    "description": "List all tracked blogs.",
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}


async def blog_list() -> str:
    """List all tracked blogs."""
    stdout, stderr, code = await _run_cli("blogs")
    if code != 0:
        return f"Failed to list blogs: {stderr}"
    return stdout or "No blogs tracked yet."


# ── Tool: blog_articles ───────────────────────────────────────

ARTICLES_TOOL_DEF: dict[str, Any] = {
    "name": "blog_articles",
    "description": (
        "List unread articles. Use all=true to include already-read articles."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "all": {
                "type": "boolean",
                "description": "Include read articles too",
                "default": False,
            },
        },
    },
}


async def blog_articles(all: bool = False) -> str:
    """List articles."""
    args = ["articles"]
    if all:
        args.append("--all")
    stdout, stderr, code = await _run_cli(*args)
    if code != 0:
        return f"Failed to list articles: {stderr}"
    return stdout or "No articles."


# ── Tool: blog_read ────────────────────────────────────────────

READ_TOOL_DEF: dict[str, Any] = {
    "name": "blog_mark_read",
    "description": "Mark an article as read by its ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "article_id": {
                "type": "string",
                "description": "Article ID to mark as read",
            },
        },
        "required": ["article_id"],
    },
}


async def blog_mark_read(article_id: str) -> str:
    """Mark an article as read."""
    stdout, stderr, code = await _run_cli("read", article_id)
    if code != 0:
        return f"Failed to mark read: {stderr}"
    return stdout or f"Marked article {article_id} as read."
