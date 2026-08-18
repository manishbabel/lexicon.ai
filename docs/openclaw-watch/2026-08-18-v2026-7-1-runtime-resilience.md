# OpenClaw Watch — 2026-08-18

## What shipped

| Stream | Version | Date | Headline |
|--------|---------|------|----------|
| Stable | **2026.7.1** (+ patches .1-1, .1-2) | 2026-07-13 | Control UI overhaul, agent delegation (`attach`), expanded model support |
| Extended-Stable | **2026.6.34** | 2026-08-08 | Hardened browser/network boundaries, idempotent channel acks, safer operator diagnostics |
| Beta | **2026.8.1-beta.2** | 2026-08-15 | Secret egress host binding, channel plugin ingress monitors, SQLite snapshot backup/restore |
| Notable prior | **2026.6.1** | 2026-06-03 | Interrupted-tool recovery, SQLite write serialization, compaction-before-overflow, guarded skill approval flows, SQLite cron migration |

Baseline was **2026.5.27** stable / **2026.5.28-beta.2** beta.

---

## What's notable

### 1. Compaction-before-overflow (2026.6.1)

OpenClaw now compacts context **before** an oversized turn is submitted rather than recovering from a failed one. The trigger is a token-count pre-check in the orchestration loop; if the projected turn size exceeds the model's context limit, the compactor runs and the turn is retried. This shifts compaction from a recovery path to a proactive guard.

### 2. SQLite write serialization for memory stores (2026.6.1)

QMD (their vector/search layer) serializes all `update`/`embed` writes per-store to eliminate `SQLITE_BUSY` contention under concurrent gateway + CLI access. The pattern is a per-store async lock wrapping every write call — not a global lock, which would serialize reads too.

### 3. Recurring cron retry after transient model rate limits (2026.6.1)

Scheduled jobs that hit model rate-limit errors now re-queue with a backoff rather than silently failing and waiting for the next scheduled window. The retry is bounded (not infinite) and uses the `retry-after` header value when present.

### 4. Secret egress host binding (2026.8.1-beta.2)

The gateway layer now maintains an allowlist of approved outbound hosts that tools/plugins may call. Attempts by untrusted tools to exfiltrate credentials to unlisted hosts are rejected at the transport layer. This is a beta feature — the binding is declared in operator config, not hardcoded.

### 5. Guarded skill approval flows (2026.6.1)

New skills submitted to the workshop go through an explicit proposal → review → approve/quarantine cycle with versioned frontmatter and hash-based rollback. An unapproved skill cannot become active even if its files land on disk. Scanner and rollback hooks fire before activation.

---

## What we can use in Lexicon

Ranked by **value / effort** (high-value items first):

### A. Compaction-before-overflow trigger — HIGH value / LOW effort

**Pattern:** Pre-check projected token count before sending a turn; if over budget, run the compactor and re-build the turn payload.

**Where in Lexicon:**
- `src/engine/orchestrator.py` — turn construction loop; add a token pre-check before dispatching to LLM
- `src/engine/context/compactor.py` — existing compactor, already callable; needs to be invoked preemptively
- `src/engine/context/token_counter.py` — provides the count

Currently `compactor.py` is called reactively (post-failure or post-turn). A single guard in `orchestrator.py` before the LLM call covers the gap with minimal new code.

---

### B. Per-store write serialization in memory manager — HIGH value / MEDIUM effort

**Pattern:** Wrap every write path (`embed`, `update`, `delete`) in a per-store `asyncio.Lock` so concurrent gateway and engine writes to the same SQLite store don't contend.

**Where in Lexicon:**
- `src/engine/memory/manager.py` — central write path; add a `_store_locks: dict[str, asyncio.Lock]` keyed by store ID
- `src/engine/memory/episodic.py` — direct writer; should route through manager or acquire the same lock
- `src/engine/memory/working.py` — same

Risk: the gateway (`src/gateway/session.py`) and the engine (`src/engine/runtime.py`) can both write memory concurrently during a turn. SQLite's WAL mode mitigates but doesn't eliminate this.

---

### C. Cron retry after rate-limit — MEDIUM value / LOW effort

**Pattern:** Catch model rate-limit errors in the cron executor and re-enqueue the job with a delay derived from `retry-after` (or a fixed backoff).

**Where in Lexicon:**
- `src/cron/scheduler.py` — job execution path; wrap the LLM call in a rate-limit handler that calls `store.reschedule(job_id, delay)`
- `src/cron/store.py` — add a `reschedule` method that updates next-run timestamp without resetting the job's full schedule

---

### D. Secret egress host binding — HIGH value / MEDIUM effort (wait for stable)

**Pattern:** Gateway declares an approved outbound host list; tool calls that attempt connections outside it are rejected before the request leaves the process.

**Where in Lexicon:**
- `src/gateway/server.py` — request pipeline; a middleware hook that checks `request.url.host` against config
- `src/shared/config.py` — add `allowed_egress_hosts: list[str]` to the config schema
- `src/engine/tools/web_search.py`, `src/engine/tools/rss_fetch.py` — tool-layer callers that would be subject to this check

Worth tracking as 2026.8.x stabilizes; shipping this before then risks churn.

---

### E. Skill quarantine / guarded activation — MEDIUM value / HIGH effort

**Pattern:** Skills don't become active until they pass a propose → review → approve cycle. Hash-based rollback on failed post-activation checks.

**Where in Lexicon:**
- `src/engine/skills.py` — skill loading path; add a `status` field (`pending | approved | quarantined`) and gate `load_skill()` on status check

This is a larger governance surface and only makes sense once Lexicon has an operator-facing skill management UI. Not a near-term spike.

---

## My picks for what to spike next

1. **Compaction-before-overflow (A)** — Highest signal-to-effort. One guard in `orchestrator.py`, uses existing `compactor.py` and `token_counter.py`. Directly improves turn reliability on long sessions.

2. **Per-store write serialization (B)** — Concrete correctness fix for a real race condition between gateway and engine. `asyncio.Lock` per store in `memory/manager.py` is a contained change.

3. **Cron retry-after-rate-limit (C)** — Low effort, immediately improves reliability of scheduled agent runs when the LLM is under load.
