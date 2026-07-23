# OpenClaw Watch — 2026-07-23

Covers releases **2026.6.1** through **2026.7.1** (stable) and **2026.7.2-beta.3** (beta).
Baseline was 2026.5.27 / 2026.5.28-beta.2.

---

## What shipped

| Version | Date | Headline |
|---|---|---|
| 2026.6.1 | 2026-06-01 | Resilient agent runs — interrupted tool calls, compaction handoffs, SQLite migration for cron/channel state, Skill Workshop proposal workflow |
| 2026.6.5 | 2026-06-05 | Provider and channel stability patches (hotfix train, no new patterns) |
| 2026.7.1 | 2026-07-01 | Gateway crash-loop prevention, wake-only-on-change scheduling, credential-log redaction hardening, session consistency across web/mobile/CLI |
| 2026.7.2-beta.1 | 2026-07-15 | Remote coding sessions on cloud workers; authorization boundary fixes |
| 2026.7.2-beta.2 | 2026-07-17 | Signal reconnection improvements; Codex CLI 0.144.4 |
| 2026.7.2-beta.3 | 2026-07-18 | Enhanced channel operation safety; guided Control UI setup for model providers |

---

## What's notable

### 1. Skill proposal workflow with hash-verified rollback (2026.6.1)
Skill Workshop introduces a `pending` state for skills — proposals are reviewed via CLI/Gateway actions before activation, carry rollback metadata and a content hash, and attach approved support files through a scanner-guarded path. This is the first formal governance layer for skill lifecycle in OpenClaw.

### 2. SQLite-serialized writes for cron / volatile state (2026.6.1)
OpenClaw migrated cron persistence, plugin install indexes, and channel thread bindings to SQLite, then added per-store write serialization to eliminate `SQLITE_BUSY` races under concurrent scheduler activity. Previously these stores were file-backed or used ad-hoc locking.

### 3. Credential and token redaction from all log surfaces (2026.6.1 + 2026.7.1)
Passwords, API keys, and OAuth tokens are now scrubbed before log write across all providers and trajectory exports. Auth failures use typed dispatch (not raw exception strings) so sensitive context never leaks into error messages.

### 4. Crash-loop prevention — stable repair path for Gateway (2026.7.1)
Gateways that fail repeatedly no longer restart indefinitely. After a configurable threshold the Gateway halts in a degraded-but-stable state with a repair signal, letting an operator (or a supervisor) intervene rather than thrashing the process.

### 5. Wake-only-on-change scheduling (2026.7.1)
Scheduled jobs can declare a change-detector. The cron runtime skips execution when no change is detected since the last successful run, logging a skip record. Useful for polling-style agents that do expensive LLM calls.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified to exist.

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---|---|---|---|
| 1 | Credential/token redaction in logger | HIGH | LOW | `src/shared/logger.py` |
| 2 | Crash-loop prevention for Gateway | HIGH | LOW | `src/gateway/server.py` |
| 3 | Skill proposal workflow + rollback metadata | HIGH | MEDIUM | `src/engine/skills.py` |
| 4 | SQLite write serialization for cron store | MEDIUM | LOW | `src/cron/store.py` |
| 5 | Wake-only-on-change cron execution | MEDIUM | MEDIUM | `src/cron/scheduler.py` |

### Notes per item

**1 — Logger redaction** (`src/shared/logger.py`): Add a `SensitiveFilter` that scrubs patterns matching bearer tokens, `api_key=`, passwords, and OAuth secrets before any log record is emitted. Adopt the typed-dispatch pattern for auth errors so stack traces never carry raw credential strings.

**2 — Gateway crash-loop guard** (`src/gateway/server.py`): Track consecutive restart count in the supervisor loop. After N failures within a window, transition to a `DEGRADED` state: stop attempting restarts, emit a structured health event, and wait for an explicit recover signal. Prevents a bad config change from pinning a CPU core.

**3 — Skill proposal workflow** (`src/engine/skills.py`): Skills currently load from the registry without review. Add a `SkillProposal` state — pending skills are stored with SHA256 hash and rollback snapshot, and only activated after explicit approval (CLI command or Gateway endpoint). Rollback re-instates the previous snapshot. High value for workspace-level skills in `workspaces/*/skills/`.

**4 — Cron write serialization** (`src/cron/store.py`): Wrap the SQLite writes in a per-store `threading.Lock` (or `asyncio.Lock` if the store is async). Low effort, prevents rare but hard-to-debug `SQLITE_BUSY` errors when the scheduler ticks while a long-running job is updating its own state.

**5 — Wake-only-on-change** (`src/cron/scheduler.py`): For jobs that poll external sources (RSS, blog monitor, openclaw-watch itself), allow a `change_key` callable that returns a hash/etag. The scheduler skips the job's execute path if the key matches the last recorded value, reducing LLM calls on idle days.

---

## My picks for what to spike next

**Spike 1 (this week) — Logger redaction in `src/shared/logger.py`**
Pure security win, zero architectural risk, ships in a single PR. Should be done before any other LLM provider key is added to Lexicon's config.

**Spike 2 (next) — Gateway crash-loop guard in `src/gateway/server.py`**
Already have the supervisor pattern in the codebase; adding restart-count tracking is additive. Makes production deployments dramatically safer when a bad skill or provider config gets pushed.
