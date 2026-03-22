"""Cron scheduler — APScheduler wrapper with session targeting (OpenClaw pattern).

Manages scheduled job execution. Each job can target:
  - "isolated": fresh agent runtime (most jobs)
  - "main": existing active session's agent
  - "system": no agent, runs a Python function directly

Lifecycle:
  1. start() — load jobs, merge defaults, register with APScheduler
  2. APScheduler fires trigger → _execute_job()
  3. _execute_job() → enqueue command or run system function
  4. stop() — shutdown APScheduler, flush state to disk

Usage:
    scheduler = CronScheduler(queue=command_queue)
    await scheduler.start()
    # ... runs in background ...
    await scheduler.stop()
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Coroutine

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.shared.logger import get_logger

from .defaults import get_default_jobs
from .store import CronJob, CronJobStore

logger = get_logger("lexicon.cron.scheduler")

# System command handlers: command string → async function
SystemHandler = Callable[[], Coroutine[Any, Any, None]]


class CronScheduler:
    """APScheduler-based cron scheduler.

    Usage:
        scheduler = CronScheduler()

        # Register system handlers (for "system" session target jobs)
        scheduler.register_system_handler("__system:prune_memory", prune_fn)

        # Register an enqueue function (for agent-targeting jobs)
        scheduler.set_enqueue_fn(enqueue_agent_run)

        await scheduler.start()
        await scheduler.stop()
    """

    def __init__(self, store: CronJobStore | None = None):
        self._store = store or CronJobStore()
        self._scheduler = AsyncIOScheduler()
        self._jobs: dict[str, CronJob] = {}  # in-memory state, id → job
        self._system_handlers: dict[str, SystemHandler] = {}
        self._enqueue_fn: Callable | None = None  # set by gateway

    # ── Configuration ─────────────────────────────────────────────

    def register_system_handler(self, command: str, handler: SystemHandler) -> None:
        """Register a handler for system commands (no agent needed).

        Example: register_system_handler("__system:prune_memory", prune_fn)
        """
        self._system_handlers[command] = handler
        logger.debug(f"Registered system handler: {command}")

    def set_enqueue_fn(self, fn: Callable) -> None:
        """Set the function used to enqueue agent runs.

        The gateway provides this — it creates an agent run in the command queue.
        Signature: async fn(agent: str, command: str, skill: str | None) -> None
        """
        self._enqueue_fn = fn

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Load jobs, merge defaults, start APScheduler."""
        # Load from disk
        stored_jobs = self._store.load()
        stored_ids = {j.id for j in stored_jobs}

        # Merge defaults — add missing defaults, keep user overrides
        defaults = get_default_jobs()
        for default in defaults:
            if default.id not in stored_ids:
                stored_jobs.append(default)
                logger.info(f"Added default cron job: {default.id}")

        # Save merged set
        self._store.save(stored_jobs)

        # Register all enabled jobs with APScheduler
        for job in stored_jobs:
            self._jobs[job.id] = job
            if job.enabled:
                self._register_job(job)

        self._scheduler.start()
        logger.info(
            f"Cron scheduler started: {len(self._jobs)} jobs "
            f"({sum(1 for j in self._jobs.values() if j.enabled)} enabled)"
        )

    async def stop(self) -> None:
        """Stop APScheduler and flush state to disk."""
        self._scheduler.shutdown(wait=False)
        self._store.save(list(self._jobs.values()))
        logger.info("Cron scheduler stopped")

    # ── Job Registration ──────────────────────────────────────────

    def _register_job(self, job: CronJob) -> None:
        """Register a single job with APScheduler."""
        trigger = self._build_trigger(job)
        if trigger is None:
            logger.error(f"Failed to build trigger for job '{job.id}'")
            return

        self._scheduler.add_job(
            func=self._execute_job,
            trigger=trigger,
            args=[job.id],
            id=job.id,
            replace_existing=True,
            name=job.description or job.id,
        )
        logger.debug(f"Registered APScheduler job: {job.id}")

    def _build_trigger(self, job: CronJob):
        """Build an APScheduler trigger from job schedule config."""
        schedule = job.schedule

        if schedule.type == "cron" and schedule.expression:
            parts = schedule.expression.split()
            if len(parts) == 5:
                return CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                    timezone=schedule.timezone,
                )
            logger.error(f"Invalid cron expression for '{job.id}': {schedule.expression}")
            return None

        elif schedule.type == "every":
            kwargs = {}
            if schedule.seconds:
                kwargs["seconds"] = schedule.seconds
            if schedule.minutes:
                kwargs["minutes"] = schedule.minutes
            if schedule.hours:
                kwargs["hours"] = schedule.hours
            if kwargs:
                return IntervalTrigger(**kwargs)
            logger.error(f"No interval specified for 'every' job '{job.id}'")
            return None

        elif schedule.type == "at" and schedule.datetime:
            return DateTrigger(run_date=schedule.datetime)

        logger.error(f"Unknown schedule type for '{job.id}': {schedule.type}")
        return None

    # ── Job Execution ─────────────────────────────────────────────

    async def _execute_job(self, job_id: str) -> None:
        """Execute a cron job. Called by APScheduler when trigger fires."""
        job = self._jobs.get(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return

        if not job.enabled:
            return

        now = datetime.utcnow().isoformat()
        logger.info(f"Cron job firing: {job_id}")

        # Update state: running
        job.state.last_run = now
        job.state.last_status = "running"
        job.state.total_runs += 1

        # Fire hook
        try:
            from src.engine.hooks import trigger_hook
            await trigger_hook("cron:fire", {
                "job_id": job_id,
                "command": job.command,
                "agent": job.target.agent,
            })
        except Exception:
            pass  # hooks are best-effort

        try:
            if job.target.session == "system":
                await self._execute_system(job)
            else:
                await self._execute_agent(job)

            # Success
            job.state.last_status = "success"
            job.state.last_error = None
            job.state.consecutive_errors = 0
            logger.info(f"Cron job complete: {job_id}")

        except Exception as e:
            # Failure
            job.state.last_status = "error"
            job.state.last_error = str(e)
            job.state.consecutive_errors += 1
            logger.error(
                f"Cron job failed: {job_id} "
                f"(consecutive errors: {job.state.consecutive_errors}): {e}"
            )

            try:
                from src.engine.hooks import trigger_hook
                await trigger_hook("cron:error", {
                    "job_id": job_id,
                    "error": str(e),
                    "consecutive_errors": job.state.consecutive_errors,
                })
            except Exception:
                pass

        # Persist state
        self._store.update_state(
            job_id,
            last_run=job.state.last_run,
            last_status=job.state.last_status,
            last_error=job.state.last_error,
            consecutive_errors=job.state.consecutive_errors,
            total_runs=job.state.total_runs,
        )

        # Fire done hook
        try:
            from src.engine.hooks import trigger_hook
            await trigger_hook("cron:done", {
                "job_id": job_id,
                "status": job.state.last_status,
            })
        except Exception:
            pass

    async def _execute_system(self, job: CronJob) -> None:
        """Execute a system command (no agent, pure Python)."""
        handler = self._system_handlers.get(job.command)
        if handler:
            await handler()
        else:
            raise RuntimeError(f"No system handler for: {job.command}")

    async def _execute_agent(self, job: CronJob) -> None:
        """Execute an agent-targeting job by enqueuing a command."""
        if not self._enqueue_fn:
            raise RuntimeError(
                "No enqueue function set. Call scheduler.set_enqueue_fn() first."
            )

        await self._enqueue_fn(
            agent=job.target.agent,
            command=job.command,
            skill=job.target.skill,
        )

    # ── CRUD (runtime management) ─────────────────────────────────

    def add_job(self, job: CronJob) -> None:
        """Add a new job (or update existing). Persists to disk."""
        self._jobs[job.id] = job
        if job.enabled:
            self._register_job(job)
        self._store.upsert(job)
        logger.info(f"Added cron job: {job.id}")

    def remove_job(self, job_id: str) -> bool:
        """Remove a job. Returns True if found."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
            self._store.remove(job_id)
            logger.info(f"Removed cron job: {job_id}")
            return True
        return False

    def enable_job(self, job_id: str) -> bool:
        """Enable a disabled job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.enabled = True
        self._register_job(job)
        self._store.upsert(job)
        return True

    def disable_job(self, job_id: str) -> bool:
        """Disable a job (keeps definition, stops scheduling)."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.enabled = False
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass
        self._store.upsert(job)
        return True

    async def run_now(self, job_id: str) -> None:
        """Force-run a job immediately (regardless of schedule)."""
        await self._execute_job(job_id)

    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """List all jobs."""
        jobs = list(self._jobs.values())
        if not include_disabled:
            jobs = [j for j in jobs if j.enabled]
        return jobs

    def get_job(self, job_id: str) -> CronJob | None:
        """Get a single job by ID."""
        return self._jobs.get(job_id)
