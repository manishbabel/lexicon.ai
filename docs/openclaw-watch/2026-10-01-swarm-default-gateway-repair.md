# OpenClaw Watch — 2026-10-01

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.9.7** | 2026-09-30 | stable | Security + reliability sweep; new model support (Fable 5.1, GPT-6 Astra, Muse Spark 1.3) |
| 2026.9.6 | 2026-09-23 | stable | macOS launch crash fix; CI/release-lane verification hardening |
| 2026.9.5 | 2026-09-19 | stable | Multi-platform reliability (Linux AppImage, Debian) |
| 2026.9.4 | 2026-09-11 | stable | Minor patch |
| 2026.9.2 | 2026-09-05 | stable | **Swarm orchestration on by default; plugin UI framework; durable restart recovery** |
| 2026.8.33 | 2026-09-29 | extended-stable | LTS security + Fable 5.1 / GPT-6 Astra support |
| **2026.8.1-beta.3** | 2026-08-24 | beta | Verified Gateway restart handoff; SQLite backup/restore; Puppeteer CDP relay |
| 2026.7.2-beta.5 | *(July)* | beta | Option-card approvals; push notifications with fair queuing |
| 2026.7.1 | 2026-07-13 | stable | **Event-driven scheduling; Gateway crash recovery path; session checkpoints** |
| 2026.6.9 | 2026-06-21 | stable | Plugin workspace pinning; transcript reader/writer seams; SQLite WAL on network FS |

Previous last-seen: stable `2026.5.27` / beta `2026.5.28-beta.2` (checked 2026-09-23).

---

## What's Notable

### 1. Swarm Orchestration as Default (2026.9.2)
Concurrent sub-agent execution flipped to the default with structured results tracking. Previously opt-in, now the assumed posture. Pairs with "keep chat responsive while heavy processing runs" — long-running operations are now explicitly decoupled from the request-response loop.

### 2. Event-Driven Scheduling (2026.7.1)
Scheduled work now wakes "only when something changes" rather than polling on a fixed clock tick. This is a pull-on-change model: the scheduler waits for a signal, fires, then re-sleeps — eliminating no-op cron iterations.

### 3. Gateway Stable Repair Path (2026.7.1 + 2026.9.7)
Repeatedly failing Gateways now enter a supervised repair path rather than restarting indefinitely. 2026.8.1-beta.3 formalises this as "explicit external Gateway lifecycle supervision with verified restart handoff" — the supervisor verifies liveness before handing back control.

### 4. Transcript Reader/Writer Seams (2026.6.9)
Clean read/write abstractions introduced over session history. Also: atomic reindex with sidecar-swap (write to temp, rename into place) to avoid partial-read windows during reindex.

### 5. Plugin Workspace Directory Pinning (2026.6.9)
Plugin working directories are now pinned at load time rather than resolved on each tool invocation, eliminating a class of race conditions when plugins are reinstalled mid-session.

---

## What We Can Use in Lexicon

Ranked by value / effort (high-value first):

### ⬛ 1 — Event-driven cron (HIGH value / LOW effort)
**Files:** `src/cron/scheduler.py`, `src/cron/store.py`

Current `scheduler.py` runs on a fixed-interval tick. Add a "dirty flag" mechanism: after each cron execution, only re-queue if a signal or state change is pending. The store (`store.py`) already persists job state — a `last_signal_at` field plus a comparison in the scheduler loop is likely all this takes.

### ⬛ 2 — Concurrent orchestration by default (HIGH value / MEDIUM effort)
**Files:** `src/engine/orchestrator.py`, `src/engine/runtime.py`

`orchestrator.py` currently sequences sub-agent calls. Introduce an `asyncio.gather` path for independent sub-agents, falling back to sequential for agents that declare dependencies. Add structured result tracking (collect `(agent_id, result, error)` tuples). The runner in `runtime.py` is already async — the change is in the orchestrator dispatch layer.

### ⬛ 3 — Gateway supervised restart (HIGH value / MEDIUM effort)
**Files:** `src/gateway/server.py`, `src/gateway/session.py`

`server.py` has no bounded retry logic — a misbehaving session can spin the process. Add an exponential-backoff supervisor loop with a max-attempts cap; after the cap, transition the session to a `DEGRADED` state and surface it rather than restarting. Mirror the "verified handoff" pattern: check session health before accepting new connections post-restart.

### ⬛ 4 — Atomic transcript reindex (MEDIUM value / LOW effort)
**Files:** `src/engine/memory/transcript_index.py`

Introduce a sidecar-swap pattern in `transcript_index.py`: write the rebuilt index to a `.tmp` path, `os.replace()` into the final path. Prevents a partial read if the process is interrupted mid-reindex.

### ⬛ 5 — Durable session recovery markers (MEDIUM value / MEDIUM effort)
**Files:** `src/engine/memory/episodic.py`, `src/engine/memory/working.py`

2026.9.2 shows that replies, settings, and plugin state survive Gateway restarts. Add a `recovery_marker` persisted to `episodic.py` at turn-commit time; on startup, `working.py` checks for an uncommitted marker and offers a resume path instead of starting a blank session.

---

## My Picks for What to Spike Next

1. **Event-driven cron** — `src/cron/scheduler.py` — highest ratio of value to code changed. One new field, one conditional. Ship this week.
2. **Atomic transcript reindex** — `src/engine/memory/transcript_index.py` — a one-function change that closes a data-corruption window. Low risk, high correctness gain.
3. **Concurrent orchestration** — `src/engine/orchestrator.py` — warrants a spike to measure wall-clock improvement on multi-agent sessions before committing to the default-on change.
