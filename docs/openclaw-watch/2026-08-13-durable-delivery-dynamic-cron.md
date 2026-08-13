# OpenClaw Watch — 2026-08-13: Durable Delivery & Dynamic Cron

**Baseline:** 2026.5.27 (stable) / 2026.5.28-beta.2 (beta)
**This digest:** 2026.7.1-2 (stable) / 2026.7.2-beta.7 (beta)
**Checked:** 2026-08-13

---

## What Shipped

| Version | Date | Channel | Headline |
|---|---|---|---|
| 2026.7.2-beta.7 | 2026-08-02 | beta | State safety, durable channels, session rewind/branch, MCP Apps, meetings, local inference, memory recall |
| 2026.7.2-beta.6 | 2026-08-01 | beta | Approvals, Fish Audio, scheduling dynamic cadence, Wear OS companion |
| 2026.7.2-beta.5 | 2026-07-28 | beta | Initial beta.7 feature wave; channel delivery durability, schema-upgrade guard |
| 2026.7.1-2 | 2026-08-04 | stable | npm plugin singleton-array metadata hotfix |
| 2026.7.1-1 | 2026-08-04 | stable | Codex progress replies, Memory Core startup recovery, WSL state permissions, plugin lock metadata |
| 2026.6.34 | 2026-08-08 | extended-stable | Security + reliability backports: sandboxed browser routes, channel acknowledgements, credential exposure, SQLite checkpoints |

---

## What's Notable

### 1. Durable Channel Delivery with Dead-Letter Recovery
OpenClaw now guarantees that in-flight channel messages (Telegram, Slack, Signal, IRC, and ~8 others) survive gateway restarts and crashes. The pattern: a *pending-work queue* written before delivery, idempotent acknowledgements on success, and a dead-letter path for unacknowledged messages. The extended-stable backport (2026.6.34) validated this as production-ready.

### 2. Per-Job Dynamic Cron Cadence + Gated Script Payloads
The scheduler now supports a `dynamic_cadence` field per job — each job can compute its next interval at runtime rather than from a static expression. Gated script payloads allow a job to declare a precondition; the scheduler skips firing if the gate is closed, avoiding phantom runs. Cron-backed heartbeat monitors also land here: named monitors that a job can signal as alive/dead.

### 3. Cross-Conversation Memory Recall (Default-On for Personal Installs)
Active-memory recall is now fast enough to run synchronously on every turn. More importantly, recall now crosses session boundaries by default on personal installs, surfacing older relevant memories that would previously have fallen out of the 7-day short-term window. Import paths from Claude Code, Codex, and Hermes are also guided.

### 4. Crash-Recoverable SQLite Snapshots + Schema-Upgrade Guard
A rollback-writer snapshot is taken before any schema migration. If the upgrade would cause data loss, it is rejected outright (not silently truncated). A quarantine store isolates the primary database from damage — corrupted rows are sidelined rather than crashing the agent.

### 5. Credential Exposure Prevention in Diagnostics
Operator diagnostic surfaces (account URLs, summaries, log output) now have a scrubbing pass that rejects credential strings before they reach any serialised log. The channel-allowlist bypass that could grant owner-level access was also closed.

---

## What We Can Use in Lexicon

Ranked by value/effort (high value first, lower effort preferred at equal value).

### #1 — Per-Job Dynamic Cadence in `src/cron/scheduler.py` ★★★ Value / ★★ Effort

**Pattern:** Add an optional `dynamic_cadence_fn` hook to `CronJob`. After each successful run `_execute_job()` calls it; if it returns a new interval, the APScheduler job is rescheduled via `_scheduler.reschedule_job()`.

**Files:** `src/cron/scheduler.py` (lines 176–256, `_execute_job`), `src/cron/store.py` (CronJob model)

**Why:** The current scheduler uses fixed `IntervalTrigger` intervals. For watch/polling jobs (like this one) the right cadence depends on whether anything changed — dynamic cadence halves wasted runs. The hook is additive; existing jobs work unchanged.

---

### #2 — Gated Script Payloads / Job Preconditions in `src/cron/scheduler.py` ★★★ Value / ★ Effort

**Pattern:** Add an optional `gate` field to `CronJob` (a command string evaluated system-side). In `_execute_job()`, evaluate the gate before firing. If the gate returns falsy, record `last_status = "skipped"` and skip enqueue.

**Files:** `src/cron/scheduler.py` (`_execute_job`, lines 177–256), `src/cron/store.py`, `src/cron/defaults.py`

**Why:** Some Lexicon cron jobs (blog watcher, paper fetch) should not fire when a session is not active or a dependency is unavailable. Today they fire regardless and produce noisy errors. A gate field is a one-struct change and a two-line check in `_execute_job`.

---

### #3 — Cross-Session Memory Recall in `src/engine/memory/manager.py` ★★★ Value / ★★★ Effort

**Pattern:** Extend `MemoryManager.recall()` to also search a transcript index beyond the 7-day `SHORT_TERM_SEARCH_LIMIT` window. The existing `src/engine/memory/transcript_index.py` is the right hook point. Add a configurable `cross_session_recall: bool` flag defaulting to `False` (safe default) with a config knob to enable it.

**Files:** `src/engine/memory/manager.py` (lines 1–50, search limits), `src/engine/memory/short_term.py`, `src/engine/memory/transcript_index.py`

**Why:** The 7-day window drops context that matters for recurring users. OpenClaw's default-on recall is aggressive; a flag lets us opt in per deployment without changing existing behaviour.

---

### #4 — SQLite Checkpoint + Schema-Upgrade Guard in `src/feedback/db.py` ★★ Value / ★ Effort

**Pattern:** Wrap the schema migration in `src/feedback/db.py` with a before/after row-count check. If any table loses rows, roll back and log a fatal. Add a `PRAGMA wal_checkpoint(TRUNCATE)` call after writes to keep WAL files from growing unbounded.

**Files:** `src/feedback/db.py` (lines 1–40, SCHEMA block and connection setup)

**Why:** `feedback.sqlite` stores session counters and term feedback. A corrupt or migrated-away table currently surfaces as silent zero-results. The guard is ~10 lines; the checkpoint call is one line.

---

### #5 — Credential Scrubbing in `src/shared/logger.py` ★★ Value / ★ Effort

**Pattern:** Add a `ScrubFilter(logging.Filter)` that redacts tokens matching common credential patterns (Bearer headers, API key prefixes, URL-embedded auth) before log records hit handlers. Attach it to the root `lexicon` logger in `setup_logger()`.

**Files:** `src/shared/logger.py` (lines 1–40, `setup_logger`)

**Why:** Lexicon logs provider calls through `src/engine/llm/` and gateway events. A misconfigured provider URL with an embedded key would currently reach `~/.lexicon/logs/gateway.log` in plaintext. A filter is ~15 lines and eliminates the class of exposure OpenClaw's 2026.6.34 backport addressed.

---

## My Picks for What to Spike Next

1. **Gated cron payloads** (item #2) — smallest change, immediate reduction in noisy failed job runs. One afternoon.
2. **Dynamic cadence** (item #1) — pairs naturally with gated payloads; reschedule after a successful run with a computed interval. One day.
3. **Credential scrubbing** (item #5) — defensive, invisible to users, eliminates a whole class of accidental exposure. Half a day.

Cross-session memory recall (#3) is the highest-impact but warrants a separate design pass to decide retention policy before enabling.
