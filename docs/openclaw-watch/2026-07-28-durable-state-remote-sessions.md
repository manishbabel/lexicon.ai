# OpenClaw Watch — 2026-07-28: Durable State & Remote Sessions

**Digest date:** 2026-07-28
**Baseline:** 2026.5.27 (stable) / 2026.5.28-beta.2 (beta)

---

## What Shipped

| Version | Type | Date | Headline |
|---|---|---|---|
| 2026.6.11 | Stable | ~Jun 11 | Intermediate stable; channel reliability and gateway fixes |
| **2026.7.1** | **Stable** | ~Jul 2026 | Full stable release: durability, channel hardening, supervised gateway |
| 2026.7.2-beta.1 | Beta | Jul 2026 | Pre-release of 7.2 series |
| 2026.7.2-beta.2 | Beta | Jul 17 | External gateway supervision, ClickClack guided setup, Skill Workshop history |
| 2026.7.2-beta.3 | Beta | Jul 18 | Remote coding sessions, native mobile automation parity, gateway recovery races |
| **2026.7.2-beta.5** | **Beta** | Jul 28 | Quarantine store, durable channel delivery, session rewind/fork, structured approvals |

**Key release notes (verbatim excerpts):**

**2026.7.2-beta.5:**
- State Safety: quarantine store protecting persisted data, crash-recoverable SQLite snapshots, schema-upgrade data-loss rejection
- Durable Channel Delivery: shared ingress drain and dead-letter recovery across Telegram, Signal, Slack, Twitch, IRC and others
- Session Management: rewind/fork conversations from individual messages, branch switching across web/native
- Interactive MCP Apps: ticketed MCP Apps with bound tools/resources, dashboard pinning, shared sandbox hardening
- Structured questions with option cards across platforms, fair queuing, headless resolution

**2026.7.2-beta.3:**
- Remote Coding Sessions: Control UI sessions on cloud workers, resume on host terminals
- Channel Safety: Telegram durable-ingress protection post-restart, Signal responsiveness during turns, channel allowlist authorization fixes
- Gateway Recovery: restart admission wedging prevention, reply session finalization stall recovery, one-shot cron job lifecycle races fixed
- External gateway supervision mode (`OPENCLAW_SUPERVISOR_MODE=external`)

---

## What's Notable

### 1. Quarantine store / crash-recoverable state
OpenClaw now writes memory/state to a quarantine sidecar before committing. If the process crashes mid-write, the quarantine store holds the last safe snapshot. Schema upgrades that would cause data loss are rejected at startup rather than silently corrupting files. This is the most significant architectural shift in the 7.x series — persistence is no longer fire-and-forget.

### 2. Dead-letter recovery for channel delivery
A shared ingress drain ensures that messages that arrive during a channel restart are buffered and replayed rather than dropped. Per-channel dead-letter queues surface delivery failures for inspection and retry instead of silently swallowing them.

### 3. Session rewind and branching
Sessions can now be rewound to any historical message and forked into a new branch. The fork carries the message history up to the rewind point and diverges from there. This enables A/B testing of agent responses and human-in-the-loop re-tries without losing prior context.

### 4. External supervisor mode
`OPENCLAW_SUPERVISOR_MODE=external` tells the gateway to skip its own crash-recovery restart logic and defer lifecycle management to an external process manager (systemd, Docker, etc). Prevents supervisor conflicts in containerised deployments.

### 5. One-shot cron lifecycle race fixes
`type: at` jobs (run-once, scheduled-datetime) were susceptible to double-fire on process restart if the job had fired but state hadn't been flushed before the crash. The fix: on startup, `type: at` jobs whose `last_run` is later than their scheduled time are skipped rather than re-queued.

---

## What We Can Use in Lexicon

Ranked by value/effort. Each entry is mapped to a real file that exists in this repo.

### 1. Atomic writes for JSONL memory stores — HIGH value / LOW effort
**Pattern:** Write to a `.tmp` sibling file, then `os.replace()` (atomic on POSIX) instead of open-append. Prevents half-written JSONL on crash.
**Files:** `src/engine/memory/short_term.py`, `src/engine/memory/episodic.py`
**Why now:** Both stores currently use JSONL append; a mid-write crash leaves the file unparseable and silently loses the session. This is a one-function change in each file.

### 2. One-shot cron race protection — HIGH value / LOW effort
**Pattern:** On `CronScheduler.start()`, for every `type: at` job, compare `job.state.last_run` against the scheduled `datetime`; if `last_run >= datetime`, mark enabled=False and skip re-registration to prevent double-fire after crash+restart.
**File:** `src/cron/scheduler.py` (lines 85–111, `start()` method and `_build_trigger()` at line 138)
**Why now:** `CronStore` persists `last_run` to disk (via `update_state` at line 239–246), so the guard data is already there — we just don't use it on restart.

### 3. Dead-letter buffer for gateway message delivery — MEDIUM value / MEDIUM effort
**Pattern:** Wrap the `CommandQueue` enqueue path in a dead-letter buffer: failed enqueues (e.g. queue full, session gone) land in an in-memory or SQLite dead-letter store rather than raising. A background task retries or surfaces them.
**Files:** `src/engine/queue.py`, `src/gateway/server.py`
**Why now:** Aligns with the 7.2-beta.5 ingress-drain pattern; Lexicon's gateway can silently drop messages when the queue lane is full.

### 4. External supervisor env var — LOW value / LOW effort
**Pattern:** Check `LEXICON_SUPERVISOR_MODE=external` in config; if set, disable the gateway's internal restart/watchdog loop and let the process exit cleanly on fatal error.
**Files:** `src/gateway/server.py`, `src/shared/config.py`
**Why now:** Containerised deployments (Docker Compose, k8s) already have an external supervisor; the internal loop conflicts with it on OOM kills.

### 5. Session message branching — LOW value / HIGH effort
**Pattern:** Store `_messages` as a tree (node: message + parent_id) rather than a flat list. A `rewind(message_id)` call creates a new branch; the session manager tracks branch head per session.
**Files:** `src/gateway/session.py`, `src/engine/runtime.py` (lines 70 `_messages` list, lines 321–333 append paths)
**Why now:** High effort relative to current Lexicon usage patterns. Useful future spike but not a quick win.

---

## My Picks for Next Spike

**Spike 1 (this week): Atomic JSONL writes** — `src/engine/memory/short_term.py` and `src/engine/memory/episodic.py`. A 5-line change per file (write to `.tmp`, rename). Eliminates a silent data-loss risk that grows with every deployed session.

**Spike 2 (this week): One-shot cron race guard** — `src/cron/scheduler.py` `start()` method. Add a 3-line check: if `DateTrigger` job has `last_run` set and it's past the scheduled datetime, set `job.enabled = False` before registering. State data is already on disk. Pure defensive win.

Both spikes are independent, testable in isolation, and require no schema changes.
