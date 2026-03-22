"""YAML frontmatter parser for markdown files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter


def parse_frontmatter(filepath: str | Path) -> tuple[dict[str, Any], str]:
    """Parse a markdown file with YAML frontmatter.

    Returns:
        (metadata_dict, body_string)
    """
    path = Path(filepath)
    if not path.exists():
        return {}, ""

    post = frontmatter.load(str(path))
    return dict(post.metadata), post.content


def parse_frontmatter_text(text: str) -> tuple[dict[str, Any], str]:
    """Parse a string with YAML frontmatter.

    Returns:
        (metadata_dict, body_string)
    """
    post = frontmatter.loads(text)
    return dict(post.metadata), post.content
