# OpenClaw Watch — 2026-11-18

Covering releases since last check (2026-09-23).

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.11.5 | 2026-11-17 | **Latest stable** | Restart-safe queues, safer update rollback, late-cron fix |
| 2026.11.4 | 2026-11-16 | Stable | 220 commits / 125 PRs / 90 contributors |
| 2026.11.3 | 2026-11 | Stable | Incremental fixes |
| 2026.11.2 | 2026-11 | Stable | Incremental fixes |
| 2026.11.1 | 2026-11-05 | Stable | Security hardening, channel reliability, session continuity |
| 2026.10.33 | 2026-11-18 | Extended-stable | On-demand skills, bounded ops, MCP-event automation |
| 2026.11.5-beta.4 | 2026-11-16 | Pre-release | Telegram widgets, automation privacy, provider recovery |

---

## What's notable

### 1. On-demand skill loading (2026.10.33)
Skills are searched and read when the agent actually needs them rather than bulk-loaded into the prompt at session start. This directly shrinks the base prompt and reduces prompt-cache misses for sessions that only use a subset of installed skills. The release notes frame it as a first-class latency and cost optimization.

### 2. Bounded memory and export operations (2026.10.33 + 2026.11.5)
All large in-flight operations — transcript reads, memory-index exports, batch embedding, snapshot compaction — now enforce explicit size bounds before they begin. The 2026.11.5 notes specifically call out OOM failures during large memory-index rebuilds and SQLite snapshot staging as fixed by bounding the work. This is a preventive pattern, not a reactive one.

### 3. Compaction credential redaction (2026.10.33)
The compactor strips credentials and secret references before summarizing long context. Without this, a summarize-and-replace step can persist API keys or tokens into the agent's permanent memory in plaintext.

### 4. Late cron wakeup protection + hot-reload safety (2026.11.5)
Two scheduling fixes that compose: (a) late-arriving scheduler wakeups no longer silently drop queued jobs, and (b) a config hot-reload mid-session no longer aborts jobs that are already running. Neither is glamorous, but both cause data loss in production without being obvious in tests.

### 5. Pre-fire permission recheck on queued automations (2026.11.5)
Before a queued automation run starts, the runtime re-validates the requesting principal's access to any private memory the job would touch. This closes a window where a permission revocation between enqueue and execution would still be honoured.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified to exist under `src/`.

### 1. On-demand skill loading — `src/engine/skills.py`
**Value: High / Effort: Low**
`src/engine/skills.py` currently loads skills at session initialization. The OpenClaw pattern is to expose a search/load interface and pull individual skills only when the routing layer signals they're relevant. In Lexicon, the tool registry at `src/engine/tools/registry.py` could serve as the index, with `src/engine/skills.py` becoming lazy. Net effect: smaller base prompt for every session.

### 2. Bounded memory operations — `src/engine/memory/manager.py`
**Value: High / Effort: Medium**
`src/engine/memory/manager.py` coordinates reads across episodic (`src/engine/memory/episodic.py`), working (`src/engine/memory/working.py`), and transcript-index (`src/engine/memory/transcript_index.py`) stores. Adding a per-operation byte or row cap before bulk reads begin mirrors OpenClaw's fix and prevents unbounded growth from becoming a runtime OOM. `src/engine/memory/search.py` is the natural chokepoint for reads.

### 3. Compaction credential redaction — `src/engine/context/compactor.py`
**Value: High / Effort: Low**
`src/engine/context/compactor.py` runs summarize-and-replace. It should strip patterns matching secrets (API keys, bearer tokens, passwords) from the summary output before it writes back to context, the same way `src/shared/logger.py` presumably redacts logs. A single pre-write filter step.

### 4. Late cron job drop protection — `src/cron/scheduler.py`
**Value: Medium / Effort: Low**
`src/cron/scheduler.py` fires jobs from `src/cron/store.py`. Adding a "job was due but not yet fired" guard on startup and a "config reload while running" check are both small invariants that prevent silent data loss without touching the scheduling model.

### 5. Queued job permission recheck — `src/engine/queue.py`
**Value: Medium / Effort: Medium**
`src/engine/queue.py` dequeues and dispatches work. Before dispatch, it should re-evaluate whether the enqueuing principal still has access to any memory or vault resources the job targets — `src/engine/memory/manager.py` for memory, `src/vault/reader.py` for vault reads. This is a defence-in-depth pattern; the enforcement point already exists, it just needs a recheck call.

---

## Picks for next spike

1. **Compaction credential redaction** (`src/engine/context/compactor.py`): Security fix, one filter function, no API surface change. Lowest-effort item with a concrete security benefit. Spike this first.

2. **On-demand skill loading** (`src/engine/skills.py` + `src/engine/tools/registry.py`): The prompt-size win compounds across every session. Requires splitting load-on-init into search-then-load but the index already exists. Good second spike.
