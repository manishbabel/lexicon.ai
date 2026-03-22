"""Default cron job definitions.

These are merged with user's jobs.json on startup.
If a default job doesn't exist in jobs.json, it's added.
If it already exists, the user's version is kept (user overrides defaults).
"""

from __future__ import annotations

from .store import CronJob, CronJobState, CronJobTarget, CronScheduleConfig


def get_default_jobs() -> list[CronJob]:
    """Return the default cron jobs shipped with Lexicon.ai."""
    return [
        CronJob(
            id="daily-paper-scan",
            description="Scan arxiv for new AI/ML papers, extract terms and patterns",
            schedule=CronScheduleConfig(
                type="cron",
                expression="0 7 * * *",  # 7am daily
            ),
            target=CronJobTarget(
                agent="software-engineer",
                skill="paper-reader",
                session="isolated",
            ),
            command=(
                "Run the paper-reader skill: scan arxiv for new papers "
                "matching our filters (AI agents, RAG, LLM infrastructure, "
                "eval/safety). Extract key terms, design patterns, and concepts. "
                "Write summaries to vault/papers/, terms to vault/terms/, "
                "design patterns to vault/patterns/, and concepts to vault/concepts/."
            ),
            enabled=True,
        ),
        CronJob(
            id="daily-blog-scan",
            description="Scan AI blogs and RSS feeds for new insights",
            schedule=CronScheduleConfig(
                type="cron",
                expression="30 7 * * *",  # 7:30am daily (after paper scan)
            ),
            target=CronJobTarget(
                agent="software-engineer",
                skill="web-researcher",
                session="isolated",
            ),
            command=(
                "Run the web-researcher skill: check RSS feeds and blogs "
                "(Anthropic, OpenAI, Simon Willison, Chip Huyen, etc.) "
                "for new posts. Extract insights, new terms, design patterns, "
                "and concepts. Write to vault/insights/, vault/terms/, "
                "vault/patterns/, and vault/concepts/."
            ),
            enabled=True,
        ),
        CronJob(
            id="nightly-consolidation",
            description="Consolidate today's episodic memory into vault patterns",
            schedule=CronScheduleConfig(
                type="cron",
                expression="0 23 * * *",  # 11pm daily
            ),
            target=CronJobTarget(
                agent="software-engineer",
                skill="knowledge-consolidator",
                session="isolated",
            ),
            command=(
                "Nightly consolidation: review today's episodic memory entries "
                "and meeting transcripts. Extract recurring design patterns, "
                "broader concepts, interesting insights, and frequently mentioned terms. "
                "Write new patterns to vault/patterns/, concepts to vault/concepts/, "
                "and update existing term files if new context was learned."
            ),
            enabled=True,
        ),
        CronJob(
            id="weekly-cleanup",
            description="Deduplicate vault terms, archive stale files, update difficulty",
            schedule=CronScheduleConfig(
                type="cron",
                expression="0 0 * * 0",  # midnight Sunday
            ),
            target=CronJobTarget(
                agent="software-engineer",
                skill="knowledge-consolidator",
                session="isolated",
            ),
            command=(
                "Weekly knowledge cleanup: "
                "1) Scan vault/terms/ for duplicate or near-duplicate entries — merge them. "
                "2) Archive vault files not accessed in 30+ days to vault/archive/. "
                "3) Update term difficulty ratings based on usage from SQLite feedback. "
                "4) Generate a weekly knowledge growth summary in vault/daily/."
            ),
            enabled=True,
        ),
        CronJob(
            id="memory-prune",
            description="Prune expired short-term memory entries (older than 7 days)",
            schedule=CronScheduleConfig(
                type="cron",
                expression="0 0 * * *",  # midnight daily
            ),
            target=CronJobTarget(
                session="system",  # No agent — pure Python, no LLM
            ),
            command="__system:prune_memory",
            enabled=True,
        ),
    ]
