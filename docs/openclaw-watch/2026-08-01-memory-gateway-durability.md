# OpenClaw Watch — 2026-08-01

**Digest slug:** memory-gateway-durability  
**Run date:** 2026-08-01  
**Previous stable:** 2026.5.27 | **Previous beta:** 2026.5.28-beta.2

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.7.1 | 2026-07-13 | **stable** | Memory durability, gateway hardening, change-gated scheduling, secret redaction |
| 2026.7.2-beta.6 | 2026-08-01 | beta | Continued stabilization of local inference, approval fair-queuing, Skill Workshop autonomy |

3,063 contributions from 532 contributors in the 2026.7.1 cycle.  
Sources: [GitHub releases](https://github.com/openclaw/openclaw/releases/tag/v2026.7.1)

---

## What's notable

### 1. Quarantine store — crash-durable memory

OpenClaw now maintains a quarantine layer alongside its primary memory store: SQLite snapshots survive primary-DB damage, and a crash-durable filesystem publication path ensures in-flight state is never silently lost. Rollback recovery with guided migration tooling was also added.

**Pattern:** write-ahead log with a secondary quarantine store; promote to primary only after confirmed flush.

### 2. Dead-letter recovery for gateway channels

Ingress messages accepted by the gateway before a crash are now guaranteed recoverable via a shared drain queue and dead-letter store. Applies to Telegram, Signal, Slack, and QQBot connectors. Previously, a gateway restart silently dropped in-flight messages.

**Pattern:** accept-then-persist before acknowledging; replay from dead-letter on restart.

### 3. Change-gated scheduling

Scheduled jobs can now declare `wake_on_change: true`, deferring execution until a watched resource or dependency actually changes. This replaces fixed-interval polling for data-dependent jobs.

**Pattern:** store a hash of the watched resource in the cron store; skip the run if unchanged.

### 4. Secret redaction hardening

Passwords and tokens are now stripped earlier in the logging pipeline. A web-search boundary bypass and a forged-marker bypass were closed. Exec and OAuth approval validation tightened; explicit approval IDs are rejected if forged.

**Pattern:** sanitize at the point of log emission, not post-hoc; treat tool boundaries as trust boundaries.

### 5. RAM-gated local inference

In-process llama.cpp GGUF support is now available with a runtime RAM check: if available system RAM falls below a configured threshold, the router falls back to the configured remote provider rather than OOM-crashing. Medium reasoning is the new default for new setups.

**Pattern:** provider router checks resource constraints before selecting local vs. remote.

---

## What we can use in Lexicon

Ranked by value/effort. Every path verified against the repo.

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---|---|---|---|
| 1 | **Secret redaction at log emission** | High | Low | `src/shared/logger.py` |
| 2 | **Change-gated cron runs** | High | Medium | `src/cron/scheduler.py`, `src/cron/store.py` |
| 3 | **Gateway dead-letter recovery** | High | Medium | `src/gateway/server.py`, `src/gateway/session.py` |
| 4 | **Memory quarantine / snapshot** | Medium | High | `src/engine/memory/manager.py`, `src/engine/memory/working.py` |
| 5 | **RAM-gated LLM routing** | Medium | High | `src/engine/llm/router.py`, `src/engine/llm/litellm_provider.py` |

### Detail

**1. Secret redaction (`src/shared/logger.py`)**  
Audit every log call site for raw token/key interpolation. Add a `redact()` sanitizer applied before `logger.info/debug/error`. Low surface area, immediate security win.

**2. Change-gated cron (`src/cron/scheduler.py`, `src/cron/store.py`)**  
`src/cron/store.py` already persists job state; add a `resource_hash` column. Before running, compare the current hash of the job's watched input to the stored one — skip execution if unchanged. `src/cron/scheduler.py` reads the gate before dispatching.

**3. Gateway dead-letter recovery (`src/gateway/server.py`, `src/gateway/session.py`)**  
On message ingress in `src/gateway/server.py`, write to a dead-letter store before processing. On startup, drain any unacknowledged messages. `src/gateway/session.py` should ack only after the session confirms receipt.

**4. Memory quarantine store (`src/engine/memory/manager.py`, `src/engine/memory/working.py`)**  
`src/engine/memory/manager.py` currently writes directly to the primary store. Add a quarantine write path: write to a quarantine table first, promote to primary after flush confirmation. `src/engine/memory/working.py` (in-process short-term state) is the natural WAL boundary.

**5. RAM-gated routing (`src/engine/llm/router.py`)**  
`src/engine/llm/litellm_provider.py` can already route to local models. Add a RAM check in `src/engine/llm/router.py`: query available system memory before selecting a provider, fallback to `claude_provider` or `openai_provider` if below threshold.

---

## Spike picks

**Spike this week:** Change-gated cron (`src/cron/scheduler.py` + `src/cron/store.py`).  
The scheduler currently runs every job on its configured interval regardless of whether the underlying data changed. A `resource_hash` check is a small schema addition plus ~20 lines in `scheduler.py` — high ROI for jobs like `rss_fetch` and `paper_fetch` that poll external sources.

**Spike next:** Secret redaction in `src/shared/logger.py`. One-day audit + sanitizer. No architecture change needed.
