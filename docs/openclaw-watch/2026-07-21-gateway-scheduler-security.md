# OpenClaw Watch — 2026-07-21

Baseline: stable `2026.5.27` / beta `2026.5.28-beta.2`
Coverage: stable `2026.7.1` (July 2026) + beta `2026.7.2-beta.3` (July 18, 2026)

---

## What shipped

### 2026.7.1 — stable (July 2026)
Headline: Control UI overhaul, gateway resilience, conditional scheduling, expanded LLM provider support (GPT-5.6, Tencent Hy3, Meta Muse Spark 1.1), 3,063 contributions from 532 contributors.

Key areas: gateway crash-loop repair, transcript compaction + session checkpointing, conditional cron wake-on-change, channel delivery durability (Telegram/Slack/Discord threading), security hardening (credential log scrubbing, untrusted provider guardrails).

### 2026.7.2-beta.1 — beta (July 15, 2026)
Cron lifecycle conflict retries preserving execution-phase decisions; Skill Workshop conservative history-based idea proposals; plugin install provenance warnings requiring `--force` for arbitrary sources; MCP server connection scoping per session; sensitive migration terminal output redaction.

### 2026.7.2-beta.3 — beta (July 18, 2026)
External gateway supervisor mode (`OPENCLAW_SUPERVISOR_MODE=external`) for lifecycle owners; gateway/session recovery preventing restart admission wedging and finalization stalls; bounded per-gateway caching; Skill Workshop auto-learning with history scanning; safer channel operations (Telegram durability, Signal reconnect after stalled handshakes).

---

## What's notable

### 1. Conditional cron: wake only when something changes
Scheduled jobs now accept a change-detection predicate. If nothing changed since last run, the job is skipped without spawning an agent. This eliminates the most common wasted cron execution: polling jobs that fire on a fixed interval even when there's nothing to do.

### 2. Gateway crash-loop → graceful repair path
Instead of restart-indefinitely on repeated failure, the gateway now enters a stable repair state and exposes a supervisor interface (`OPENCLAW_SUPERVISOR_MODE=external`). External processes (systemd, Docker, k8s) can own the restart lifecycle; the gateway itself signals health rather than self-restarting.

### 3. Cron lifecycle conflict retries preserve execution-phase decisions
When two scheduled jobs claim the same execution slot (clock skew, resume after sleep), the retry logic now preserves which phase (claim → execute → finalize) each job was in before the conflict. Jobs don't restart from scratch; they resume from the last consistent checkpoint.

### 4. Sensitive output redaction in logs and migration output
Passwords and tokens are now actively scrubbed from log records and terminal output during migrations/setup. The pattern uses a log filter that rewrites known credential patterns (bearer tokens, DB URLs, API keys) before they reach any handler.

### 5. Plugin/skill install provenance gating
Installing a skill or plugin from an arbitrary source now requires an explicit `--force` flag; known-registry installs are unchanged. This makes the default safe and surfaces provenance questions at install time rather than at runtime.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified to exist in `src/`.

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---------|-------|--------|-----------------|
| 1 | **Conditional cron wake-on-change** — skip job execution if no input changed since last run | High | Low | `src/cron/scheduler.py`, `src/cron/store.py` |
| 2 | **Credential scrubbing log filter** — strip tokens/passwords from all log records before handlers fire | High | Low | `src/shared/logger.py` |
| 3 | **Cron conflict-retry preserving execution phase** — retry conflicting jobs from their last phase checkpoint, not from the start | Medium | Low | `src/cron/scheduler.py`, `src/cron/store.py` |
| 4 | **Gateway health-signal + supervisor handoff** — gateway exposes explicit health/repair states; lifecycle managed externally | High | Medium | `src/gateway/server.py` |
| 5 | **Skill install provenance gating** — require explicit confirmation for out-of-registry skill sources | Medium | Medium | `src/engine/skills.py` |

---

## My picks for what to spike next

**Spike 1 — Conditional cron (`src/cron/scheduler.py`):** Add an optional `condition` callable to `CronScheduler`. Before spawning an agent, call `condition()` and skip if it returns `False`. Immediate payoff: the RSS-fetch and blog-watcher cron jobs currently fire even when feeds haven't updated. Low risk, contained to the cron subsystem.

**Spike 2 — Credential scrubbing filter (`src/shared/logger.py`):** Add a `logging.Filter` subclass that rewrites `Authorization: Bearer <token>`, `postgres://<user>:<pass>@`, and similar patterns with `***REDACTED***`. Attach it to the root logger in `setup_logger()`. One-hour job, zero architecture change.
