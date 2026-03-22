"""Vault writer — write .md files to the Obsidian vault with YAML frontmatter.

Handles papers, terms, and insights. Files are written to ~/.lexicon/vault/
and QMD auto-indexes them for hybrid search.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

from src.shared.constants import VAULT_DIR
from src.shared.logger import get_logger

logger = get_logger("lexicon.vault.writer")

# 8 valid categories
VALID_CATEGORIES = [
    "llm-foundations",
    "agents",
    "rag-and-retrieval",
    "evals-and-quality",
    "infra-and-serving",
    "context-engineering",
    "products-and-platforms",
    "design-patterns",
]

VALID_DIFFICULTIES = ["beginner", "intermediate", "advanced"]


def slugify(text: str) -> str:
    """Convert text to a URL/filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _ensure_dir(path: Path) -> None:
    """Ensure a directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def _write_md(path: Path, metadata: dict[str, Any], body: str) -> Path:
    """Write a markdown file with YAML frontmatter."""
    post = frontmatter.Post(body, **metadata)
    content = frontmatter.dumps(post)
    path.write_text(content, encoding="utf-8")
    logger.info(f"Wrote vault file: {path}")
    return path


def write_paper(
    title: str,
    authors: list[str],
    url: str,
    category: str,
    tags: list[str],
    summary: str,
    key_findings: list[str],
    new_terms: list[str],
    practical_takeaway: str,
    patterns: list[str] | None = None,
    relevance: str = "high",
    paper_date: date | None = None,
    vault_dir: Path | None = None,
) -> Path:
    """Write a paper note to vault/papers/.

    Returns the path of the written file.
    """
    vault = vault_dir or VAULT_DIR
    papers_dir = vault / "papers"
    _ensure_dir(papers_dir)

    today = paper_date or date.today()
    slug = slugify(title)
    filename = f"{today.isoformat()}-{slug}.md"
    path = papers_dir / filename

    metadata = {
        "title": title,
        "authors": authors,
        "date": today.isoformat(),
        "url": url,
        "category": category,
        "tags": tags,
        "relevance": relevance,
    }

    # Build body following extraction template
    lines = [f"# {title}", ""]
    lines += ["## Summary", summary, ""]
    lines += ["## Key Findings"]
    for f in key_findings:
        lines.append(f"- {f}")
    lines += [""]
    lines += ["## New Terms"]
    for t in new_terms:
        lines.append(f"- {t}")
    lines += [""]
    lines += ["## Practical Takeaway", practical_takeaway, ""]
    if patterns:
        lines += ["## Patterns & Approaches"]
        for p in patterns:
            lines.append(f"- {p}")

    body = "\n".join(lines)
    return _write_md(path, metadata, body)


def write_term(
    term: str,
    definition: str,
    use_in_sentence: str,
    category: str,
    difficulty: str = "intermediate",
    related: list[str] | None = None,
    context_tags: list[str] | None = None,
    source: str = "learned",
    key_points: list[str] | None = None,
    gotchas: list[str] | None = None,
    vault_dir: Path | None = None,
) -> Path:
    """Write a term note to vault/terms/.

    Returns the path of the written file.
    """
    vault = vault_dir or VAULT_DIR
    terms_dir = vault / "terms"
    _ensure_dir(terms_dir)

    slug = slugify(term)
    path = terms_dir / f"{slug}.md"

    metadata = {
        "term": term,
        "category": category,
        "difficulty": difficulty,
        "related": related or [],
        "context_tags": context_tags or [],
        "source": source,
        "created": date.today().isoformat(),
    }

    lines = [f"# {term}", ""]
    lines += [f"**Definition:** {definition}", ""]
    lines += ["## Use in Sentence", f'"{use_in_sentence}"', ""]

    if key_points:
        lines += ["## Key Points"]
        for p in key_points:
            lines.append(f"- {p}")
        lines += [""]

    if gotchas:
        lines += ["## Gotchas"]
        for g in gotchas:
            lines.append(f"- {g}")
        lines += [""]

    if related:
        lines += ["## Related"]
        for r in related:
            lines.append(f"- [[{r}]]")

    body = "\n".join(lines)
    return _write_md(path, metadata, body)


def write_insight(
    title: str,
    source_url: str,
    source_type: str,
    category: str,
    tags: list[str],
    summary: str,
    key_points: list[str],
    terms_mentioned: list[str] | None = None,
    vault_dir: Path | None = None,
) -> Path:
    """Write a blog/article insight to vault/insights/.

    Returns the path of the written file.
    """
    vault = vault_dir or VAULT_DIR
    insights_dir = vault / "insights"
    _ensure_dir(insights_dir)

    today = date.today()
    slug = slugify(title)
    filename = f"{today.isoformat()}-{slug}.md"
    path = insights_dir / filename

    metadata = {
        "title": title,
        "source_url": source_url,
        "source_type": source_type,
        "category": category,
        "tags": tags,
        "date": today.isoformat(),
    }

    lines = [f"# {title}", ""]
    lines += ["## Summary", summary, ""]
    lines += ["## Key Points"]
    for p in key_points:
        lines.append(f"- {p}")

    if terms_mentioned:
        lines += ["", "## Terms"]
        for t in terms_mentioned:
            lines.append(f"- [[{t}]]")

    body = "\n".join(lines)
    return _write_md(path, metadata, body)


def write_pattern(
    name: str,
    category: str,
    problem: str,
    solution: str,
    diagram: str,
    components: list[str],
    trade_offs: list[str],
    when_to_use: str,
    say_this: str = "",
    related: list[str] | None = None,
    tags: list[str] | None = None,
    source: str = "",
    vault_dir: Path | None = None,
) -> Path:
    """Write a design pattern note to vault/patterns/.

    Returns the path of the written file.
    """
    vault = vault_dir or VAULT_DIR
    patterns_dir = vault / "patterns"
    _ensure_dir(patterns_dir)

    slug = slugify(name)
    path = patterns_dir / f"{slug}.md"

    metadata = {
        "pattern": name,
        "category": category,
        "tags": tags or [],
        "related": related or [],
        "source": source,
        "created": date.today().isoformat(),
    }

    lines = [f"# {name}", ""]
    lines += ["## Problem", problem, ""]
    lines += ["## Solution", solution, ""]
    if diagram:
        lines += ["## Diagram", "```", diagram, "```", ""]
    lines += ["## Components"]
    for c in components:
        lines.append(f"- {c}")
    lines += [""]
    lines += ["## Trade-offs"]
    for t in trade_offs:
        lines.append(f"- {t}")
    lines += [""]
    lines += ["## When to Use", when_to_use, ""]
    if say_this:
        lines += ["## Say This", f'"{say_this}"', ""]
    if related:
        lines += ["## Related"]
        for r in related:
            lines.append(f"- [[{r}]]")

    body = "\n".join(lines)
    return _write_md(path, metadata, body)


def write_concept(
    name: str,
    definition: str,
    category: str,
    key_ideas: list[str],
    how_it_works: str = "",
    say_this: str = "",
    related: list[str] | None = None,
    tags: list[str] | None = None,
    source: str = "",
    difficulty: str = "intermediate",
    vault_dir: Path | None = None,
) -> Path:
    """Write a concept note to vault/concepts/.

    Concepts are broader than terms — things like 'attention mechanism',
    'prompt chaining', 'retrieval-augmented generation' that need more
    explanation than a single definition.

    Returns the path of the written file.
    """
    vault = vault_dir or VAULT_DIR
    concepts_dir = vault / "concepts"
    _ensure_dir(concepts_dir)

    slug = slugify(name)
    path = concepts_dir / f"{slug}.md"

    metadata = {
        "concept": name,
        "category": category,
        "difficulty": difficulty,
        "tags": tags or [],
        "related": related or [],
        "source": source,
        "created": date.today().isoformat(),
    }

    lines = [f"# {name}", ""]
    lines += [f"**Definition:** {definition}", ""]
    if how_it_works:
        lines += ["## How It Works", how_it_works, ""]
    lines += ["## Key Ideas"]
    for idea in key_ideas:
        lines.append(f"- {idea}")
    lines += [""]
    if say_this:
        lines += ["## Say This", f'"{say_this}"', ""]
    if related:
        lines += ["## Related"]
        for r in related:
            lines.append(f"- [[{r}]]")

    body = "\n".join(lines)
    return _write_md(path, metadata, body)


def vault_file_exists(subdir: str, slug: str, vault_dir: Path | None = None) -> bool:
    """Check if a vault file already exists."""
    vault = vault_dir or VAULT_DIR
    path = vault / subdir / f"{slug}.md"
    return path.exists()
