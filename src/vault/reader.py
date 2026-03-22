"""Vault reader — read and parse .md files from the Obsidian vault."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.shared.constants import VAULT_DIR
from src.shared.frontmatter import parse_frontmatter
from src.shared.logger import get_logger

logger = get_logger("lexicon.vault.reader")


def read_file(path: str, vault_dir: Path | None = None) -> dict[str, Any]:
    """Read a vault file and return its metadata + body.

    Args:
        path: Relative path within vault (e.g. "terms/rag.md") or absolute path.
        vault_dir: Override vault directory (default: ~/.lexicon/vault).

    Returns:
        {"metadata": {...}, "body": "...", "path": "..."}
    """
    vault = vault_dir or VAULT_DIR

    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = vault / path

    if not file_path.exists():
        return {"metadata": {}, "body": "", "path": str(file_path), "error": "File not found"}

    metadata, body = parse_frontmatter(file_path)
    return {
        "metadata": metadata,
        "body": body.strip(),
        "path": str(file_path),
    }


def list_files(
    subdir: str = "",
    category: str | None = None,
    vault_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """List vault files in a subdirectory, optionally filtered by category.

    Args:
        subdir: Subdirectory to list (e.g. "terms", "papers"). Empty = all.
        category: Filter by frontmatter category field.
        vault_dir: Override vault directory.

    Returns:
        List of {"name": "...", "path": "...", "metadata": {...}}
    """
    vault = vault_dir or VAULT_DIR
    search_dir = vault / subdir if subdir else vault

    if not search_dir.exists():
        return []

    results = []
    for md_file in sorted(search_dir.rglob("*.md")):
        metadata, _ = parse_frontmatter(md_file)

        if category and metadata.get("category") != category:
            continue

        results.append({
            "name": md_file.stem,
            "path": str(md_file.relative_to(vault)),
            "metadata": metadata,
        })

    return results


def search_by_field(
    subdir: str,
    field: str,
    value: str,
    vault_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Search vault files where a frontmatter field matches a value.

    Supports string fields (exact match) and list fields (contains match).

    Returns:
        List of {"name": "...", "path": "...", "metadata": {...}, "body": "..."}
    """
    vault = vault_dir or VAULT_DIR
    search_dir = vault / subdir

    if not search_dir.exists():
        return []

    results = []
    for md_file in sorted(search_dir.rglob("*.md")):
        metadata, body = parse_frontmatter(md_file)
        field_value = metadata.get(field)

        if field_value is None:
            continue

        # List field: check if value is in the list
        if isinstance(field_value, list):
            if value not in field_value:
                continue
        # String field: case-insensitive match
        elif str(field_value).lower() != value.lower():
            continue

        results.append({
            "name": md_file.stem,
            "path": str(md_file.relative_to(vault)),
            "metadata": metadata,
            "body": body.strip(),
        })

    return results
