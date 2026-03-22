"""Smoke test: load workspace → send prompt → get Claude response → print.

Run: uv run python -m scripts.smoke_test
"""

import asyncio

from src.engine.llm.claude_provider import ClaudeProvider
from src.engine.registry import AgentRegistry
from src.shared.config import get_settings
from src.shared.logger import setup_logger

logger = setup_logger("lexicon.smoke_test")


async def main():
    settings = get_settings()
    model = settings.software_engineer_llm_model or settings.default_llm_model

    # Check API key
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY not set. Add it to .env or ~/.lexicon/config.json")
        return
    if not model:
        logger.error(
            "No Claude model configured. Set SOFTWARE_ENGINEER_LLM_MODEL "
            "or DEFAULT_LLM_MODEL in .env or ~/.lexicon/config.json"
        )
        return

    logger.info("=== Lexicon.ai Smoke Test ===")

    # 1. Create LLM provider
    llm = ClaudeProvider(default_model=model)
    logger.info("Claude provider created")

    # 2. Create registry and register software-engineer agent
    registry = AgentRegistry(llm=llm)
    agent = registry.create(
        agent_id="test-swe",
        persona="software-engineer",
        model=model,
    )
    logger.info(f"Agent created: {agent.config.id}")
    logger.info(f"Workspace loaded from: {agent.config.workspace_path}")
    logger.info(f"Identity: {agent.workspace.identity[:100]}...")

    # 3. Run a test prompt
    test_prompt = (
        "Someone in my meeting just said: 'We need to figure out how to make our LLM "
        "use company documentation instead of making things up.' "
        "Give me a suggestion and some terms I can use."
    )

    logger.info(f"Sending test prompt: {test_prompt[:80]}...")
    print("\n--- Agent Response ---\n")

    full_response = ""
    async for output in agent.run(test_prompt):
        if output.type == "text_delta":
            print(output.delta, end="", flush=True)
            full_response += output.delta
        elif output.type == "done":
            break

    print("\n\n--- End Response ---")
    logger.info(f"Response length: {len(full_response)} chars")
    logger.info("Smoke test PASSED")


if __name__ == "__main__":
    asyncio.run(main())
