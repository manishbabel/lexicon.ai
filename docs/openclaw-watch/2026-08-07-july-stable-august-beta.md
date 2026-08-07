# OpenClaw Watch — 2026-08-07

## What Shipped

| Release | Date | Type |
|---|---|---|
| **2026.7.1-2** | 2026-08-04 | Stable (latest) |
| 2026.7.1-1 | 2026-08-04 | Stable (patch) |
| 2026.7.1 | ~2026-07 | Stable |
| **2026.7.2-beta.7** | 2026-08-02 | Beta (latest) |
| 2026.7.2-beta.6 | 2026-08-01 | Beta |
| 2026.7.2-beta.5 | 2026-07-28 | Beta |
| 2026.7.2-beta.4–1 | Jul–Aug | Beta |

Previous seen: **2026.6.11** stable / **2026.7.1-beta.1** beta.

### 2026.7.1-x (Stable) — headline
Reliability sweep: Memory Core startup repair resolving legacy-index conflicts on load; WSL EROFS state-permission tolerance; Codex terminal progress-reply continuity across app-server turns; NPM plugin singleton-array metadata acceptance.

### 2026.7.2-beta.7 (Beta — latest) — headline
Major infrastructure cycle across the full beta series: crash-recoverable memory stores with quarantine pattern; durable dead-letter channel delivery across restarts; per-job dynamic scheduling cadence; memory fast recall with cross-conversation seed; session rewind/fork; interactive MCP Apps; structured agent questions with option cards; Teams/Zoom/Google Meet integration; local llama.cpp/Gemma inference with RAM gating; Claude Opus 5 + Kimi K3 provider additions; Fish Audio S2.1 synthesis.

---

## What's Notable

### 1. Crash-recoverable memory quarantine (2026.7.2-beta series)
When SQLite-backed memory state is corrupted (partial write, schema mismatch, disk-full mid-flush), the runtime moves the damaged store to a `quarantine/` path, bootstraps a fresh empty store, and continues startup rather than crashing hard. Snapshot writes use a write-then-rename atomic pattern: new state goes to `state.tmp`, then `os.replace()` to the final path. Schema upgrades reject if the upgrade would silently drop populated columns.

### 2. Dead-letter channel delivery with ingress drain (2026.7.2-beta series)
Inbound channel messages (Telegram, Signal, Slack, QQBot, IRC, Zalo, Twitch) are written to a durable ingress log before being routed to the agent. On restart the runtime drains unprocessed entries from the log before opening new channel connections, so no message is lost across restarts. Messages that fail delivery after N retries move to a dead-letter store surfaced in the dashboard.

### 3. Per-job dynamic scheduling cadence (2026.7.2-beta series)
Each scheduled job can now write its preferred `next_fire_at` back to the schedule store; the scheduler reads per-job cadence at dispatch time rather than a global cron expression. Durable schedule-source streaming keeps the job list in sync across restarts without manual re-registration. Jobs can self-throttle (slow down when idle) or self-accelerate (speed up when queues are backlogged).

### 4. Memory fast recall + cross-conversation seed (2026.7.2-beta series)
A compact "fast recall" ranked list (top-K by access frequency) is maintained alongside the full episodic store. When a new session starts, these K items are seeded into working memory before the first turn — the agent doesn't cold-start. Memory retrieval now explicitly distinguishes the fast path (pre-loaded) from deep search (async MMR over the full store).

### 5. Memory Core startup conflict resolution (2026.7.1 stable)
Companion to the quarantine story: stable made memory startup idempotent by detecting and resolving legacy-index conflicts (duplicate embedding entries, schema version mismatches) on load rather than propagating corrupted state into the first agent turn. Establishes the pattern: validate and self-repair index state before the first agent turn, always.

---

## What We Can Use in Lexicon

Ranked by **value / effort**. Every path verified in the working tree.

### 1. Memory atomic-write + quarantine — HIGH value / LOW effort
**File:** `src/engine/memory/manager.py`
**Also:** `src/engine/memory/episodic.py`

`MemoryManager` writes state but has no crash-recovery guard — a write interrupted mid-flush leaves the store in a partially-written state that blocks the next startup. Port two things together: (a) atomic write: flush to `state.tmp` then `os.replace()` to the target path; (b) startup quarantine: if the store fails to open or validate on load, move it to `state.quarantine-<timestamp>` and bootstrap fresh. One-time addition that eliminates the "agent won't start after crash" class of bug entirely.

---

### 2. Memory startup conflict resolution — HIGH value / LOW effort
**File:** `src/engine/memory/manager.py`

Add a `_resolve_conflicts()` step in `MemoryManager.__init__` (or `load()`): scan for duplicate embedding rows (same content hash, multiple IDs), detect schema-version mismatches, and either heal or quarantine before the first agent turn. Pairs naturally with the atomic-write fix above — same file, minimal surface area.

---

### 3. Per-job scheduling cadence — HIGH value / MEDIUM effort
**Files:** `src/cron/scheduler.py`, `src/cron/store.py`

`CronScheduler` dispatches all jobs on a shared global tick. Add a `next_fire_at` field to `src/cron/store.py`'s job record and a `reschedule_after(job_id, delay_s)` method callable from within a running job. `scheduler.py` reads `next_fire_at` per job at dispatch time and skips if it hasn't elapsed. Enables vault-sync and memory-indexing jobs to self-throttle when idle and catch up when backlogged — no polling overhead.

---

### 4. Durable ingress drain for gateway channels — MEDIUM value / MEDIUM effort
**Files:** `src/gateway/router.py`, `src/gateway/session.py`

Gateway sessions accept messages but have no durability layer — a restart between receive and dispatch drops the message silently. Port the ingress-drain pattern: write inbound messages to an append-only log (a small SQLite table in the cron store or a separate file) before routing them. On startup, drain the log before accepting new connections. Wire a dead-letter path for messages that fail after N retries. Especially useful for Lexicon's audio pipeline, where a recording completion event must not be lost.

---

### 5. Memory fast recall + session seed — MEDIUM value / MEDIUM effort
**Files:** `src/engine/memory/working.py`, `src/engine/memory/search.py`

Add a `fast_recall` ranked list (top-K by access frequency, updated on each retrieval in `search.py`) alongside the full episodic index. Expose `WorkingMemory.seed_from_fast_recall(k)` called at session start before the first tool dispatch. Annotate pre-seeded items distinctly from runtime-retrieved items so the agent knows what is "always on" vs. what was searched. Eliminates the cold-start cost for users with established memory.

---

## My Picks to Spike Next

1. **Memory atomic-write + quarantine** (`src/engine/memory/manager.py`) — two small changes in one file, eliminates the worst class of startup failure. Ship first.
2. **Memory startup conflict resolution** (`src/engine/memory/manager.py`) — pairs with above, same file, low incremental effort.
3. **Per-job scheduling cadence** (`src/cron/scheduler.py`, `src/cron/store.py`) — medium effort, high leverage for vault-sync and indexing jobs that currently block on a shared global tick.
