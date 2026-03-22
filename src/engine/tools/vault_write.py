"""Vault write tool — agent tool wrapper around vault.writer.

Allows the agent to write papers, terms, and insights to the Obsidian vault.
"""

from __future__ import annotations

from typing import Any

from src.shared.logger import get_logger
from src.vault.writer import write_concept, write_insight, write_paper, write_pattern, write_term

logger = get_logger("lexicon.engine.tools.vault_write")


async def vault_write(path: str, content: dict[str, Any]) -> str:
    """Write a file to the vault.

    Args:
        path: Target subdirectory — "papers", "terms", "insights", "patterns", or "concepts".
        content: Dict with fields matching the target type.

    Returns:
        Success message with the written file path, or error message.
    """
    try:
        if path == "papers":
            file_path = write_paper(
                title=content["title"],
                authors=content.get("authors", []),
                url=content.get("url", ""),
                category=content.get("category", ""),
                tags=content.get("tags", []),
                summary=content.get("summary", ""),
                key_findings=content.get("key_findings", []),
                new_terms=content.get("new_terms", []),
                practical_takeaway=content.get("practical_takeaway", ""),
                patterns=content.get("patterns"),
                relevance=content.get("relevance", "high"),
            )
            return f"Paper written to: {file_path}"

        elif path == "terms":
            file_path = write_term(
                term=content["term"],
                definition=content["definition"],
                use_in_sentence=content.get("use_in_sentence", ""),
                category=content.get("category", ""),
                difficulty=content.get("difficulty", "intermediate"),
                related=content.get("related"),
                context_tags=content.get("context_tags"),
                source=content.get("source", "learned"),
                key_points=content.get("key_points"),
                gotchas=content.get("gotchas"),
            )
            return f"Term written to: {file_path}"

        elif path == "insights":
            file_path = write_insight(
                title=content["title"],
                source_url=content.get("source_url", ""),
                source_type=content.get("source_type", "blog"),
                category=content.get("category", ""),
                tags=content.get("tags", []),
                summary=content.get("summary", ""),
                key_points=content.get("key_points", []),
                terms_mentioned=content.get("terms_mentioned"),
            )
            return f"Insight written to: {file_path}"

        elif path == "patterns":
            file_path = write_pattern(
                name=content["name"],
                category=content.get("category", "design-patterns"),
                problem=content.get("problem", ""),
                solution=content.get("solution", ""),
                diagram=content.get("diagram", ""),
                components=content.get("components", []),
                trade_offs=content.get("trade_offs", []),
                when_to_use=content.get("when_to_use", ""),
                say_this=content.get("say_this", ""),
                related=content.get("related"),
                tags=content.get("tags"),
                source=content.get("source", ""),
            )
            return f"Pattern written to: {file_path}"

        elif path == "concepts":
            file_path = write_concept(
                name=content["name"],
                definition=content["definition"],
                category=content.get("category", ""),
                key_ideas=content.get("key_ideas", []),
                how_it_works=content.get("how_it_works", ""),
                say_this=content.get("say_this", ""),
                related=content.get("related"),
                tags=content.get("tags"),
                source=content.get("source", ""),
                difficulty=content.get("difficulty", "intermediate"),
            )
            return f"Concept written to: {file_path}"

        else:
            return f"Unknown vault path: {path}. Use 'papers', 'terms', 'insights', 'patterns', or 'concepts'."

    except KeyError as e:
        return f"Missing required field: {e}"
    except Exception as e:
        logger.error(f"vault_write failed: {e}")
        return f"Error writing to vault: {e}"


# Tool definition for the registry
TOOL_DEF = {
    "name": "vault_write",
    "description": (
        "Write to the Obsidian vault knowledge base. "
        "Set 'path' to 'papers', 'terms', 'insights', 'patterns', or 'concepts'. "
        "Set 'content' to a JSON object with the required fields for that type. "
        "Papers need: title, authors, url, category, tags, summary, key_findings, new_terms, practical_takeaway. "
        "Terms need: term, definition, use_in_sentence, category, difficulty, related. "
        "Insights need: title, source_url, source_type, category, tags, summary, key_points. "
        "Patterns need: name, category, problem, solution, diagram (ASCII), components, trade_offs, when_to_use, say_this. "
        "Concepts need: name, definition, category, key_ideas, how_it_works, say_this, difficulty."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "enum": ["papers", "terms", "insights", "patterns", "concepts"],
                "description": "Target vault subdirectory",
            },
            "content": {
                "type": "object",
                "description": "Content fields for the vault entry",
            },
        },
        "required": ["path", "content"],
    },
}
