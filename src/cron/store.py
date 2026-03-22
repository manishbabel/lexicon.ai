"""Cron job store — read/write jobs.json (OpenClaw pattern).

Persistence layer for cron job definitions + runtime state.
Jobs are stored in ~/.lexicon/cron/jobs.json as a single JSON file.

The file holds both the definition (schedule, target, command) and
mutable runtime state (last_run, errors, total_runs) in one place.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.shared.constants import CRON_DIR
from src.shared.logger import get_logger

logger = get_logger("lexicon.cron.store")

JOBS_FILE = CRON_DIR / "jobs.json"


# ── Models ────────────────────────────────────────────────────────

class CronScheduleConfig(BaseModel):
    """Schedule configuration for a cron job.

    Three types (from OpenClaw):
      "at"    — one-shot at specific datetime
      "every" — interval (minutes/hours/seconds)
      "cron"  — cron expression (most flexible)
    """
    type: Literal["at", "every", "cron"]

    # For "at" schedule
    datetime: str | None = None  # ISO datetime string

    # For "every" schedule
    seconds: int | None = None
    minutes: int | None = None
    hours: int | None = None

    # For "cron" schedule
    expression: str | None = None  # e.g. "0 7 * * *"
    timezone: str | None = None    # e.g. "America/New_York"


class CronJobTarget(BaseModel):
    """Where a cron job runs."""
    agent: str = "software-engineer"          # Which agent persona
    skill: str | None = None                  # Hint: which skill to activate
    session: Literal["isolated", "main", "system"] = "isolated"


class CronJobState(BaseModel):
    """Mutable runtime state for a cron job."""
    last_run: str | None = None               # ISO datetime
    next_run: str | None = None               # ISO datetime
    last_status: Literal["success", "error", "running", None] = None
    last_error: str | None = None
    consecutive_errors: int = 0
    total_runs: int = 0


class CronJob(BaseModel):
    """A complete cron job definition + state."""
    id: str
    description: str = ""
    schedule: CronScheduleConfig
    target: CronJobTarget = Field(default_factory=CronJobTarget)
    command: str = ""                         # The input text for the agent
    enabled: bool = True
    state: CronJobState = Field(default_factory=CronJobState)


# ── Store ─────────────────────────────────────────────────────────

class CronJobStore:
    """Read/write cron jobs from ~/.lexicon/cron/jobs.json.

    Usage:
        store = CronJobStore()
        jobs = store.load()
        store.save(jobs)
        store.upsert(job)
        store.remove("job-id")
    """

    def __init__(self, path: Path | None = None):
        self._path = path or JOBS_FILE
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[CronJob]:
        """Load all jobs from disk."""
        if not self._path.exists():
            return []

        try:
            data = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read jobs.json: {e}")
            return []

        raw_jobs = data.get("jobs", [])
        jobs = []
        for raw in raw_jobs:
            try:
                jobs.append(CronJob(**raw))
            except Exception as e:
                logger.warning(f"Skipping invalid job entry: {e}")

        logger.debug(f"Loaded {len(jobs)} cron jobs from {self._path}")
        return jobs

    def save(self, jobs: list[CronJob]) -> None:
        """Save all jobs to disk (full rewrite)."""
        data = {
            "jobs": [job.model_dump(mode="json") for job in jobs],
        }
        self._path.write_text(json.dumps(data, indent=2, default=str) + "\n")
        logger.debug(f"Saved {len(jobs)} cron jobs to {self._path}")

    def upsert(self, job: CronJob) -> None:
        """Add or update a job by ID."""
        jobs = self.load()
        existing_idx = next(
            (i for i, j in enumerate(jobs) if j.id == job.id), None
        )
        if existing_idx is not None:
            jobs[existing_idx] = job
        else:
            jobs.append(job)
        self.save(jobs)

    def remove(self, job_id: str) -> bool:
        """Remove a job by ID. Returns True if found."""
        jobs = self.load()
        filtered = [j for j in jobs if j.id != job_id]
        if len(filtered) == len(jobs):
            return False
        self.save(filtered)
        logger.info(f"Removed cron job: {job_id}")
        return True

    def get(self, job_id: str) -> CronJob | None:
        """Get a single job by ID."""
        for job in self.load():
            if job.id == job_id:
                return job
        return None

    def update_state(self, job_id: str, **state_updates: Any) -> None:
        """Update just the state fields of a job (without reloading everything).

        Usage: store.update_state("daily-paper-scan", last_run="2026-03-19T07:00:12Z", last_status="success")
        """
        jobs = self.load()
        for job in jobs:
            if job.id == job_id:
                for key, value in state_updates.items():
                    if hasattr(job.state, key):
                        setattr(job.state, key, value)
                self.save(jobs)
                return
        logger.warning(f"Job not found for state update: {job_id}")
