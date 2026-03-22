"""CLI script to seed the Lexicon vault with starter terms.

Usage:
    uv run python scripts/seed_terms.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports resolve.
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.shared.constants import VAULT_DIR
from src.seeds.load_seeds import load_seed_terms


def main() -> None:
    # Ensure vault/terms/ directory exists
    terms_dir = VAULT_DIR / "terms"
    terms_dir.mkdir(parents=True, exist_ok=True)

    print(f"Seeding terms into {terms_dir} ...")
    count = load_seed_terms()
    print(f"Done. {count} new term(s) written.")


if __name__ == "__main__":
    main()
