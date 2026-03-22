"""Term feedback tool — agent tool wrapper around feedback.terms CRUD.

Allows the agent to record how the user interacts with suggested terms:
used (adopted it), dismissed (rejected it), or suggested (system proposed it).
"""

from __future__ import annotations

from src.feedback.terms import bump_dismissed, bump_suggested, bump_used
from src.shared.logger import get_logger

logger = get_logger("lexicon.engine.tools.term_feedback")

_ACTION_MAP = {
    "used": bump_used,
    "dismissed": bump_dismissed,
    "suggested": bump_suggested,
}


async def term_feedback(term: str, action: str, notes: str | None = None) -> str:
    """Record feedback for a term.

    Args:
        term: The term slug to record feedback for.
        action: One of "used", "dismissed", "suggested".
        notes: Optional free-text note (logged but not stored in DB).

    Returns:
        Confirmation string.
    """
    handler = _ACTION_MAP.get(action)
    if handler is None:
        return f"Unknown action '{action}'. Use 'used', 'dismissed', or 'suggested'."

    try:
        handler(term)
        if notes:
            logger.info(f"term_feedback: {action} '{term}' — {notes}")
        return f"Recorded '{action}' feedback for term '{term}'."
    except Exception as e:
        logger.error(f"term_feedback failed: {e}")
        return f"Error recording feedback: {e}"


# Tool definition for the registry
TOOL_DEF = {
    "name": "term_feedback",
    "description": (
        "Record feedback on a vocabulary term. "
        "Use action 'used' when the user adopts the term in conversation, "
        "'dismissed' when the user rejects a suggestion, "
        "or 'suggested' when the system proposes the term. "
        "Optionally include notes for context."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "term": {
                "type": "string",
                "description": "The term slug to record feedback for",
            },
            "action": {
                "type": "string",
                "enum": ["used", "dismissed", "suggested"],
                "description": "The type of feedback to record",
            },
            "notes": {
                "type": "string",
                "description": "Optional free-text note for context",
            },
        },
        "required": ["term", "action"],
    },
}
