# OpenClaw Watch — 2026-08-19

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.7.1** + patches -1, -2 | ~2026-08-04 | Stable | Gateway resilience, credential hygiene, change-triggered scheduling, channel expansion |
| **2026.6.34** | 2026-08-08 | Extended-Stable | Security hardening, channel recovery, safer operator diagnostics |
| **2026.7.2-beta.7** | ~2026-08-02 | Beta | State quarantine store, durable channel delivery, session rewind/branching |
| **2026.8.1-beta.2** | 2026-08-15 | Beta | Secret egress host binding, atomic model/runtime switching, SQLite snapshot backup |

Since baseline (2026.5.27 / 2026.5.28-beta.2), OpenClaw shipped 6+ builds. Four carry patterns worth porting.

## What's Notable

### 1. Gateway crash-loop prevention → stable repair path (2026.7.1)
Repeatedly failing gateways no longer spin in an infinite restart loop; they enter a structured repair path instead. Related: session group recovery paths, transcript cache rotation, and persistence fixes for stale cross-session state.

### 2. Credential sanitization in logs (2026.7.1 + 2026.8.1-beta.2)
"Passwords and tokens stay out of more logs" (7.1) paired with "secret egress host binding" (8.1-beta.2). Addresses leakage of API keys through debug log paths and egress monitoring.

### 3. Change-triggered scheduling (2026.7.1)
Jobs can now wake "only when something changes" — a condition/event trigger alongside the existing time-based ones. Reduces wasted cycles for watch-style jobs.

### 4. State quarantine store + crash recovery (2026.7.2-beta.7)
Durable write path with a quarantine store so partially-written state survives crashes without corrupting the main store. Pairs with durable channel delivery across gateway restarts.

### 5. Atomic model/runtime switching (2026.8.1-beta.2)
Hot-swap of LLM provider or model at runtime without tearing down active sessions. No observed downtime on in-flight requests.

## What We Can Use in Lexicon

Ranked by value/effort. All file paths verified against the current `src/` tree.

---

### #1 — Credential scrubbing in `src/shared/logger.py` ★ Top spike

**Value: High / Effort: Low**

`src/shared/logger.py` passes log messages through as plain `f"{...}"` strings with no redaction. API keys appear in `~/.lexicon/logs/gateway.log` whenever they surface in an exception message or a `logger.debug(f"... key={key}")` call. The `/api/deepgram-key` REST endpoint in `src/gateway/server.py:391` also returns a raw key.

Port: add a `ScrubFormatter` that replaces known-key patterns (32+ char hex/alphanumeric tokens) with `[REDACTED]` before writing to the file handler. Attach it only to the `FileHandler`, not stdout, to keep dev UX intact.

---

### #2 — Cron consecutive-error circuit-breaker in `src/cron/scheduler.py` ★

**Value: Medium / Effort: Low**

`src/cron/scheduler.py:220-226` already tracks `consecutive_errors` and logs it — but takes no further action. A job that throws on every fire keeps hammering at full frequency forever. OpenClaw 2026.6.34 added cron circuit-breaking that pauses jobs after N consecutive failures and re-enables after a cooling period.

Port: in `_execute_job` (line 177), after incrementing `consecutive_errors`, auto-disable the job when it exceeds a threshold (e.g. 5) and schedule a one-shot re-enable via `DateTrigger`. Already has the `disable_job` / `enable_job` hooks (lines 302, 308) — trivial wiring.

---

### #3 — Gateway startup failure recovery in `src/gateway/server.py`

**Value: Medium / Effort: Medium**

The `lifespan()` context manager (line 60) creates all services synchronously — if any step fails, the process crashes with no recovery path. OpenClaw 7.1's repair path wraps each service init in a try/except, logs degraded state, and exposes a `/health` endpoint that reports which services are unavailable so the operator can act without a full restart.

Port: wrap each numbered service init (lines 69–137) in individual `try/except` blocks; set service globals to `None` on failure; update `/health` (line 341) to report service status rather than a flat `{"status": "ok"}`.

---

### #4 — Atomic JSONL writes in `src/engine/memory/` (from 2026.7.2-beta.7 quarantine store)

**Value: Medium / Effort: Medium**

`src/engine/memory/short_term.py` and `src/engine/memory/episodic.py` append directly to JSONL files. A crash mid-write truncates the last record silently. OpenClaw's quarantine store pattern: write to a `.tmp` sidecar, fsync, rename atomically. On startup, any orphaned `.tmp` files are either replayed (if complete) or discarded.

Port: introduce a `safe_append(path, entry)` helper used by both `ShortTermMemory` and `EpisodicMemory`.

---

### #5 — Change-triggered cron schedule type in `src/cron/`

**Value: Medium / Effort: High**

`src/cron/scheduler.py:138` supports `cron`, `every`, and `at` trigger types. OpenClaw's watch-style jobs fire only when a tracked resource changes (file mtime, HTTP ETag, DB row count). This would let Lexicon's cron jobs skip firing when there's nothing to report.

Port: add a `watch` schedule type to `src/cron/store.py`'s `CronSchedule` model; implement a `WatchTrigger` adapter in `_build_trigger` (line 138) that wraps an APScheduler `IntervalTrigger` with a pre-check condition callable. Requires exposing a "condition fn" registration API on `CronScheduler` analogous to `register_system_handler`.

## My Picks for What to Spike Next

1. **`src/shared/logger.py` — ScrubFormatter** (1–2h). Highest security value, lowest effort. Required before any key is ever written to `gateway.log`.
2. **`src/cron/scheduler.py` — consecutive-error circuit-breaker** (1h). The scaffolding is already there; this is pure wiring. Prevents runaway cron failure storms.
3. **`src/gateway/server.py` — per-service degraded startup** (half-day). Makes the gateway operationally observable and self-healing without a full process restart.
