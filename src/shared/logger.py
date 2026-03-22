"""Structured logging setup."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from .constants import LOGS_DIR


def setup_logger(
    name: str = "lexicon",
    level: str = "INFO",
    log_to_file: bool = True,
) -> logging.Logger:
    """Create a structured logger.

    Logs to stdout always, and optionally to ~/.lexicon/logs/gateway.log.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Don't add handlers if they already exist
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # File handler
    if log_to_file:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOGS_DIR / "gateway.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "lexicon") -> logging.Logger:
    """Get an existing logger or create one."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger
