# OpenClaw Watch — 2026-08-09: Runtime Recovery & Durable Delivery

## What shipped

| Release | Date | Type |
|---|---|---|
| **2026.6.34** | Aug 8, 2026 | Extended-stable maintenance |
| **2026.7.1-1** | Aug 4, 2026 | Stable patch |
| **2026.7.1-2** | Aug 4, 2026 | Stable npm fix |
| **2026.7.2-beta.7** | Aug 2, 2026 | Beta feature |
| **2026.7.2-beta.6** | Aug 1, 2026 | Beta feature |
| **2026.7.2-beta.5** | Jul 28, 2026 | Beta feature |

Baseline was stable **2026.5.27** / beta **2026.5.28-beta.2**.

### Headline changes from release notes

**2026.7.2-beta.7** (major):
- State safety: quarantine storage for DB damage, crash-recoverable SQLite snapshots, rollback-writer snapshot recovery
- Durable channel delivery: message recovery across gateway restarts for Telegram, Signal, Slack, Discord, and more
- Session rewind/branching: fork conversations from individual messages, switch transcript branches
- Dynamic scheduling: per-job cadence adjustment and heartbeat monitors
- Structured approvals: question cards with options across web + channel platforms
- Local inference: in-process llama.cpp/Gemma support with local provider detection
- New models: Claude Opus 5, Kimi K3, GPT Live realtime

**2026.6.34** (extended-stable hardening):
- Sandboxed browser/network routes reject unsafe access paths; credentials scrubbed from account URLs
- Resilient agent runs: retained session writes, provider fallbacks, stream progress recovery
- Idempotent channel ACKs: pending work resumes after recovery, Discord burst buffering bounded
- Dependency security updates: brace-expansion, PostCSS, Undici

**2026.7.1-1**:
- Memory Core startup repair: recovers from legacy-index conflicts without crash

---

## What's notable

**1. Crash-recoverable memory snapshots (quarantine + rollback)**
OpenClaw now writes a SQLite snapshot before any destructive operation and moves corrupt state into a quarantine store rather than failing hard. On restart, it detects the quarantine and replays cleanly. This is not a hotfix — it's a first-class recovery path built into the memory layer.

**2. Idempotent channel delivery with per-message ACKs**
Delivery now survives gateway restarts: messages are written to a pending store before the channel send, removed only on ACK, and ACKs are idempotent so retries are safe. The 2026.6.34 stable release back-ported the ACK pattern without the full quarantine machinery.

**3. Session branching (conversation forking)**
Sessions can now fork at any prior message, creating a divergent transcript branch. The branch is a first-class entity tracked by session ID — it isn't a copy, it shares history up to the fork point.

**4. Dynamic per-job cadence + heartbeat monitors**
Jobs can adjust their own interval at runtime (e.g., back off on repeated failures, speed up on fresh data). Each job gets a lightweight heartbeat monitor that fires if the job goes silent for N consecutive periods — no more silent cron death.

**5. Network boundary hardening with credential scrubbing**
Loopback and custom browser origin endpoints now validate against an allowlist before executing. URLs passed to diagnostics/logging have credentials stripped. This is the security hardening in 2026.6.34 — it closed an owner-escalation vector via channel allowlists.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified against the repo.

### 1. Memory write-ahead + quarantine recovery
**Value: High | Effort: Medium**

Lexicon's `src/engine/memory/short_term.py` and `src/engine/memory/episodic.py` both append directly to JSONL files with no rollback path. A partial write during a crash leaves the file in an unparseable state.

Port: before each append, write to a `.tmp` file, then atomically rename. On startup in `src/engine/memory/manager.py`, detect `.tmp` residue and either complete or discard. No quarantine store needed yet — atomic rename is 90% of the win.

### 2. Idempotent delivery receipts in the command queue
**Value: High | Effort: Medium**

`src/engine/queue.py` fires-and-forgets to the LLM layer with no delivery confirmation. If the gateway restarts mid-run (e.g., `src/gateway/session.py` tears down), the in-flight command is lost silently.

Port: add a `delivered_at` timestamp and a `nack` path to `QueueMode`. Commands entering the queue get a UUID; the runtime ACKs on first successful tool call. The cron lane in `src/cron/scheduler.py` is the most critical target — job fires but no one knows if it ran.

### 3. Per-job heartbeat monitors in the cron scheduler
**Value: Medium | Effort: Low**

`src/cron/scheduler.py` wraps APScheduler with no self-check. If a job hangs (e.g., QMD query blocking), the scheduler's thread is consumed silently.

Port: in `CronScheduler._execute_job()`, record a heartbeat timestamp to the `CronJobStore`. Add a watchdog coroutine that checks for jobs exceeding `2 × interval` with no heartbeat and emits a warning log + optional alert. The store at `src/cron/store.py` already persists job state — just add a `last_heartbeat` field.

### 4. Network boundary allowlist in web_search tool
**Value: Medium | Effort: Low**

`src/engine/tools/web_search.py` dispatches outbound requests with no domain allowlist or credential-scrubbing before logging. The 2026.6.34 pattern rejects requests to loopback/internal ranges and strips `Authorization` headers from log output.

Port: add a `BLOCKED_DOMAINS` constant and a pre-flight check before the HTTP call. Strip `Authorization` / `Cookie` headers from any URL that gets passed to `src/shared/logger.py`.

### 5. Session branching scaffold
**Value: Medium | Effort: High**

`src/gateway/session.py` supports create/pause/resume/end but no forking. The pattern from 2026.7.2-beta.7 tracks a `parent_session_id` and `fork_message_index` on the new session, then slices the conversation history at that index to seed the child.

Port: add `fork_session(session_id, from_message_index)` to `SessionManager`. This is higher effort because `src/engine/runtime.py` would need to accept a pre-seeded conversation slice rather than always starting fresh. Defer unless conversation forking is on the near-term product roadmap.

---

## My picks for what to spike next

**Spike 1 — Atomic memory writes** (`src/engine/memory/short_term.py`, `src/engine/memory/episodic.py`): pure correctness improvement, no API surface change, testable in isolation. Do this first.

**Spike 2 — Cron heartbeat monitor** (`src/cron/scheduler.py`, `src/cron/store.py`): one field + one coroutine. Closes the silent-job-death gap that's probably causing unexplained skips in production already.

**Spike 3 — Queue delivery receipts** (`src/engine/queue.py`): more involved but the right foundation before any channel expansion (Slack/Discord integration would make missing receipts a visible user-facing bug).
