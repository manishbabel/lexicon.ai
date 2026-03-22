"""Run database migrations — create tables and indexes."""

import asyncio

from src.db.migrations import run_migrations
from src.db.pool import create_pool, close_pool
from src.shared.logger import setup_logger

logger = setup_logger("lexicon.migrations")


async def main():
    logger.info("Starting database migrations...")
    pool = await create_pool()
    try:
        await run_migrations(pool)
        logger.info("Migrations completed successfully")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
