# OpenClaw Watch — 2026-07-24: Gateway Resilience & Event-Driven Cron

## What shipped

| Version | Date | Type |
|---|---|---|
| 2026.7.1 | 2026-07-13 | Stable (promoted to `npm latest`, replacing 2026.6.11) |
| 2026.7.2-beta.1 | 2026-07-15 | Beta |
| 2026.7.2-beta.2 | 2026-07-17 | Beta |
| 2026.7.2-beta.3 | 2026-07-18 | Beta |

**Baseline**: 2026.5.27 stable / 2026.5.28-beta.2

### 2026.7.1 headline changes
- **Gateway crash-loop hardening**: repeatedly failing Gateways now enter a stable repair path instead of restarting indefinitely.
- **Event-driven scheduling**: scheduled jobs can be configured to wake only when watched state actually changes, eliminating fixed-interval polling.
- **Session groups + checkpoints**: Gateway-backed session groups with fork/archive/rename/unread-state tracking; checkpoints persist across web, mobile, and CLI.
- **Security tightening**: untrusted responses now filtered earlier in the pipeline; unsafe network requests and file downloads blocked at the boundary; approval scope limits narrowed.
- **Model & provider expansion**: Claude Sonnet 5, GPT-5.6, Meta Muse Spark 1.1, ClawRouter; Featherless provider added.
- 2,018 merged PRs, 532 contributors.

### 2026.7.2-beta.3 headline changes (incremental on 7.1)
- **Cloud workers**: session placement and routing to remote sandboxed workers.
- **Cron history**: run-level history stored and queryable per job.
- **Coding-agent memory imports**: bulk import of external memory corpora into agent memory at session start.
- **Authorization boundary improvements**: tighter per-agent capability scope at the gateway level.
- **Enhanced channel safety**: guarded teardown for Telegram, Slack, Discord, Apple Messages during in-flight operations.

---

## What's notable

### 1. Event-driven cron (change-triggered wakeup)
OpenClaw's scheduler now supports a `wake_on_change` mode: a job declares a watcher (file, key-value record, webhook event) and is only invoked when the watched value changes. This eliminates the most common failure mode of interval-polling crons — redundant executions and thundering-herd bursts. The pattern is additive; fixed-interval jobs are unchanged.

### 2. Gateway crash-loop recovery with repair state machine
Instead of a simple restart-on-error loop, the gateway now tracks consecutive failure count and, beyond a threshold, enters a `REPAIRING` state: it stops accepting new sessions, drains in-flight ones, runs a self-check routine, and only re-enters `RUNNING` once the check passes. This prevents the worst operational failure mode (gateway soft-locks the host process).

### 3. Cron run history in the store
Each cron execution now appends a structured record (trigger time, result, duration, error if any) to a persistent store. This enables audit trails, failure diagnosis, and "last-good-run" queries without external observability tooling.

### 4. Untrusted-response filtering at the gateway boundary
Tool responses (especially from external/third-party MCP tools) are now filtered for injection patterns before being forwarded to the agent runtime. This is a defense-in-depth layer: the gateway is the right chokepoint because it handles all tool traffic regardless of which skill invoked the tool.

### 5. Coding-agent memory imports
A new bootstrap hook allows agents to import structured memory corpora (e.g. prior session transcripts, external knowledge bases) at start time. This replaces ad-hoc seeding approaches and gives a defined lifecycle hook: `memory.import(source, strategy)` before the first turn.

---

## What we can use in Lexicon

Ranked by value/effort. File paths verified against the repo.

### [HIGH value / LOW effort] Event-driven cron wakeup
**File**: `src/cron/scheduler.py`

Current Lexicon cron fires on fixed intervals (`src/cron/defaults.py`). Add a `WatchedJob` variant alongside the existing `CronJob`: it takes a `watcher_fn` callable and only enqueues the job when `watcher_fn()` returns a changed value (compared to last run). No external deps — pure Python. This eliminates unnecessary agent runs for jobs like openclaw-watch itself.

### [HIGH value / LOW effort] Cron run history
**File**: `src/cron/store.py`

The store already exists but likely tracks only job registration. Extend it to persist a per-job `runs` list: `{triggered_at, completed_at, status, error}`. Bounded ring buffer (last N runs) to avoid unbounded growth. Pairs naturally with the `WatchedJob` pattern above.

### [HIGH value / MEDIUM effort] Gateway crash-loop recovery
**File**: `src/gateway/server.py`

Add a consecutive-failure counter to the gateway startup/restart loop. Beyond a configurable threshold (e.g. 3), transition to a `REPAIRING` state: stop accepting new sessions, wait for in-flight sessions to drain (with a timeout), run a lightweight health check, then re-enter `RUNNING`. This prevents the process from consuming resources in a tight restart loop.

### [MEDIUM value / LOW effort] Untrusted tool response filtering
**File**: `src/gateway/protocol.py`

Add a `sanitize_tool_response(response)` pass in the protocol layer before tool results are forwarded to the engine runtime. Start with a simple blocklist of injection markers (e.g. `<system>`, `<admin>`, prompt-injection patterns). The gateway is already the right chokepoint.

### [MEDIUM value / HIGH effort] Memory import hook at session start
**Files**: `src/engine/memory/manager.py`, `src/engine/runtime.py`

Define a `MemoryImportSource` protocol and a `memory.import()` call triggered during session initialization (before the first turn). The memory manager already handles episodic, working, and short-term memory; import is additive. Most useful for workspaces that bootstrap from large external corpora (`workspaces/ai-educator/KNOWLEDGE-BASE.md` is the clearest existing case).

---

## My picks for what to spike next

1. **Event-driven cron** (`src/cron/scheduler.py`) — this is a direct improvement to how openclaw-watch itself runs. Spike a `WatchedJob` that compares last-seen version against current; eliminates the weekly no-op runs.

2. **Cron run history** (`src/cron/store.py`) — a natural companion to #1, almost no risk. Add the runs list to the store schema; gives immediate operational visibility.

3. **Gateway crash-loop recovery** (`src/gateway/server.py`) — investigate whether the current server has any restart logic; if it's a bare `while True: restart()` loop, the fix is small and high impact.
