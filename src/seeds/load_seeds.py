"""Load seed terms into the Obsidian vault.

Reads SEED_TERMS and writes each as a .md file to VAULT_DIR/terms/
using the vault writer. Skips terms that already exist on disk.
"""

from __future__ import annotations

from src.shared.constants import VAULT_DIR
from src.shared.logger import get_logger
from src.vault.writer import slugify, write_term

logger = get_logger("lexicon.seeds")


def load_seed_terms() -> int:
    """Write seed terms to the vault, skipping any that already exist.

    Returns the number of new terms written.
    """
    from src.seeds.terms_seed import SEED_TERMS

    terms_dir = VAULT_DIR / "terms"
    written = 0

    for entry in SEED_TERMS:
        slug = slugify(entry["term"])
        target = terms_dir / f"{slug}.md"

        if target.exists():
            logger.debug(f"Skipping existing term: {entry['term']}")
            continue

        write_term(
            term=entry["term"],
            definition=entry["definition"],
            use_in_sentence=entry.get("use_in_sentence", ""),
            category=entry["category"],
            difficulty=entry.get("difficulty", "intermediate"),
            related=entry.get("related_terms"),
            context_tags=entry.get("context_tags"),
            source="preloaded",
        )
        written += 1
        logger.info(f"Seeded term: {entry['term']}")

    logger.info(f"Seed complete: {written} new terms written, {len(SEED_TERMS) - written} skipped")
    return written
