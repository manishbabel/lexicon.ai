# OpenClaw Watch — 2026-07-17

Covers stable **2026.7.1** (2026-07-13) and beta **2026.7.2-beta.2** (2026-07-17).  
Previous baseline: stable 2026.5.27, beta 2026.5.28-beta.2.

---

## What shipped

### 2026.7.1 (stable, 2026-07-13)
3 063 contributions from 532 contributors. Headline themes: Control UI overhaul, expanded model support (GPT-5.6, Tencent Hy3, Meta Muse Spark 1.1), and infrastructure hardening.

- **Gateway crash-loop prevention** — repeatedly-failing gateways now park in a stable degraded state instead of restarting indefinitely.
- **Credential hygiene** — passwords and tokens scrubbed from more log paths; unsafe downloads blocked earlier.
- **Channel reliability** — Telegram, Slack, Discord, Signal, WhatsApp, Teams, Matrix all received progress-visibility, media-handling, and delivery-reliability fixes.
- **Coding-agent delegation** — `openclaw attach` grants temporary session access to external coding agents (Claude Code, Codex); native subagent tracking added.

### 2026.7.2-beta.1 (beta, 2026-07-15)
- **External gateway supervision** — new `OPENCLAW_SUPERVISOR_MODE=external` flag lets lifecycle owners (OCM, systemd) own restart decisions instead of the gateway looping on itself.
- **Restart admission gate** — gateway rejects a re-initialization if it detects a prior instance still wedged, preventing duplicate-process races.
- **Cron claim-race recovery** — one-shot cron jobs that lose a lifecycle claim slot now retry with back-off rather than silently skipping.
- **ClickClack integration** — guided CLI setup with URL/token prompts; native commands published to composer autocomplete.

### 2026.7.2-beta.2 (beta, 2026-07-17)
- **Terminal coding sessions** — Codex/Claude catalog sessions resume from embedded node host via duplex terminal commands.
- **Skill Workshop: agent-init bypass** — actions initiated by the agent itself no longer require a secondary approval prompt by default.
- **iOS offline chat** — pre-painted from a bounded, protected per-gateway cache; session recovery after finalization stalls.
- **Slack progress** — uses native assistant-thread status with rotating loading messages instead of plain text polling.

---

## What's notable (patterns worth tracking)

### 1. Gateway crash-loop guard
**What:** Before each restart attempt, the gateway checks a failure counter. After _N_ consecutive failures within a window it stops looping, emits a structured "degraded" event, and waits for an external signal or operator intervention. The companion `SUPERVISOR_MODE=external` flag delegates the restart decision entirely to the process supervisor.

**Why it matters:** Self-restarting servers that loop on a config error or broken dependency fill logs, consume resources, and make the failure harder to diagnose. A parked-degraded state is observable and recoverable; a crash loop is neither.

### 2. Cron claim-race retry for one-shot jobs
**What:** One-shot (`"at"` schedule) jobs that fire near the same millisecond as a scheduler restart previously risked double-claiming or silently dropping. OpenClaw now wraps the claim with a compare-and-swap on a `claimed_by` field and retries with jitter on conflict; the decision (run/skip) is persisted before execution begins.

**Why it matters:** Lexicon's `CronScheduler` uses APScheduler's `DateTrigger` for one-shot jobs and persists state in `CronJobStore` as plain JSON. There is no claim gate — a scheduler restart near a fire time can lose or duplicate a run.

### 3. Skills: agent-initiated action bypass
**What:** OpenClaw's Skill Workshop tags invocations with an `initiated_by` field (`"agent"` vs `"user"`). Agent-initiated invocations skip the secondary approval prompt. The registry enforces this at dispatch, not inside each skill.

**Why it matters:** Lexicon's skill system (`src/engine/skills.py`) currently has no notion of who initiated a skill. Adding an `initiated_by` field at the registry dispatch layer would allow the orchestrator to suppress redundant approval gates for chained skill calls.

### 4. SQLite WAL mode gated on filesystem type
**What:** OpenClaw detects whether the database path lives on a network filesystem and disables WAL mode in that case (falling back to DELETE journaling). The check uses `os.statvfs` flags.

**Why it matters:** Lexicon's `src/feedback/db.py` opens `~/.lexicon/feedback.sqlite` without configuring a journal mode. If `~/.lexicon` is on NFS (common in shared dev containers and some macOS setups), WAL mode causes locking failures. A one-time check at `get_connection()` would prevent silent data corruption.

### 5. Compactor: usage-counter preservation across compaction
**What:** OpenClaw snapshots the current token usage totals before the compaction LLM call, then adds the snapshot back to the post-compaction running total. Without this, compaction LLM calls inflate the session's reported token spend.

**Why it matters:** Lexicon's `src/engine/context/compactor.py` compacts via LLM but does not snapshot usage before the call. The compaction LLM calls count against the session's token totals, inflating cost estimates and potentially triggering premature pruning.

---

## What we can use in Lexicon

Ranked by value/effort (high value first, lower effort preferred at equal value):

| # | Pattern | Value | Effort | File(s) |
|---|---------|-------|--------|---------|
| 1 | Gateway crash-loop guard | High | Low | `src/gateway/server.py` |
| 2 | Cron one-shot claim-race retry | High | Medium | `src/cron/scheduler.py`, `src/cron/store.py` |
| 3 | SQLite WAL gated on filesystem type | Medium | Low | `src/feedback/db.py` |
| 4 | Compactor usage-counter snapshot | Medium | Medium | `src/engine/context/compactor.py` |
| 5 | Skills agent-initiated bypass | Low–Medium | Low | `src/engine/skills.py` |

### Detail

**1 — Gateway crash-loop guard** (`src/gateway/server.py`)  
Add a `_restart_failures: int` counter to the gateway lifespan. On each failed startup, increment. If `_restart_failures >= 3` within 60 s, log a structured `DEGRADED` event and `sys.exit(1)` rather than looping. Pair with an env var `LEXICON_SUPERVISOR_MODE=external` that makes the gateway never self-restart. This is a small addition to the existing `asynccontextmanager` lifespan block.

**2 — Cron one-shot claim-race retry** (`src/cron/scheduler.py`, `src/cron/store.py`)  
For `"at"` schedule jobs: before `_execute_job` enqueues the run, write a `claimed_at` timestamp to the job record with a conditional write (skip if already set). On APScheduler restart, check `claimed_at` — if set and within the last 60 s, skip the fire. This prevents duplicate runs after a hot-reload or gateway bounce mid-fire.

**3 — SQLite WAL gate** (`src/feedback/db.py`)  
In `get_connection()`, after opening the connection, check `os.statvfs(DB_PATH.parent).f_flags` for `ST_RDONLY` or known NFS magic numbers. If network filesystem detected, skip the `PRAGMA journal_mode=WAL` call and log a warning. No WAL → no cross-host locking deadlocks.

**4 — Compactor token snapshot** (`src/engine/context/compactor.py`)  
Before calling the LLM for summarization, snapshot the provider's cumulative token counters. After the compaction completes, subtract the compaction's own tokens from the session total (or track them under a separate `compaction_tokens` budget). This keeps session cost estimates clean.

**5 — Skills agent-init bypass** (`src/engine/skills.py`)  
Add an optional `initiated_by: Literal["agent", "user"] = "user"` parameter to the dispatch path. Pass `"agent"` when a skill is invoked from within an orchestrator turn rather than a direct user message. The registry can expose this to callers; individual skills don't need to change.

---

## My picks for what to spike next

1. **Gateway crash-loop guard** — lowest risk, highest operational value. A one-afternoon change that prevents the most common production outage pattern (misconfigured model key → infinite restart → container OOM).

2. **Cron one-shot claim-race retry** — Lexicon already has `CronStore.save()` writing full state; adding a `claimed_at` field to the model and one conditional check in `_execute_job` closes a real gap before scheduled daily jobs scale up.
