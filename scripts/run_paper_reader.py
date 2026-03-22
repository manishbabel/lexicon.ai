#!/usr/bin/env python3
"""Run the paper-reader skill on a given arxiv paper.

Usage:
    python scripts/run_paper_reader.py https://arxiv.org/abs/2401.12345
    python scripts/run_paper_reader.py 2401.12345

This creates an agent with the software-engineer persona, loads the
paper-reader skill, and runs it against the given paper URL. Results
are written to ~/.lexicon/vault/ (papers/ and terms/).
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.engine.llm.openai_provider import OpenAIProvider
from src.engine.registry import AgentRegistry
from src.engine.tools.setup import setup_tools
from src.shared.constants import VAULT_DIR


async def run_paper_reader(paper_url: str) -> None:
    """Run the paper-reader skill on a single paper."""
    print(f"\n{'='*60}")
    print(f"Paper Reader — processing: {paper_url}")
    print(f"Vault: {VAULT_DIR}")
    print(f"{'='*60}\n")

    # Ensure vault directories exist
    for subdir in ["papers", "terms", "insights"]:
        (VAULT_DIR / subdir).mkdir(parents=True, exist_ok=True)

    # Create agent with tools
    llm = OpenAIProvider()
    registry = AgentRegistry(llm=llm)
    runtime = registry.create(
        agent_id="paper-reader-manual",
        persona="software-engineer",
        max_tokens=4096,
    )

    # Wire tools into the runtime
    tool_registry = setup_tools()
    tool_registry.wire_into_runtime(runtime)

    # Build the prompt — tell the agent to use the paper-reader skill
    prompt = (
        f"Read and process this arxiv paper: {paper_url}\n\n"
        "Use the read_skill tool to load the 'paper-reader' skill for instructions. "
        "Follow the skill's instructions exactly:\n"
        "1. Fetch the paper using paper_fetch\n"
        "2. Check if relevant using the filters\n"
        "3. Extract knowledge following the extraction template\n"
        "4. Write paper note and term notes to the vault using vault_write\n"
        "5. Search for duplicate terms before creating new ones using qmd_search\n\n"
        "Process the paper completely."
    )

    # Run the agent
    print("Running agent...\n")
    async for output in runtime.run(prompt):
        if output.type == "text_delta":
            print(output.delta, end="", flush=True)
        elif output.type == "tool_result":
            print(f"\n[Tool: {output.tool_name}] → {str(output.tool_result)[:200]}")
        elif output.type == "done":
            print("\n\n✓ Done.")
        elif output.type == "error":
            print(f"\n✗ Error: {output.error}")

    # Show what was written
    print(f"\n{'='*60}")
    print("Vault contents:")
    for subdir in ["papers", "terms"]:
        d = VAULT_DIR / subdir
        if d.exists():
            files = list(d.glob("*.md"))
            if files:
                print(f"\n  {subdir}/")
                for f in sorted(files):
                    print(f"    - {f.name}")
    print(f"{'='*60}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_paper_reader.py <arxiv-url-or-id>")
        print("Example: python scripts/run_paper_reader.py https://arxiv.org/abs/2401.12345")
        sys.exit(1)

    paper_url = sys.argv[1]
    asyncio.run(run_paper_reader(paper_url))


if __name__ == "__main__":
    main()
