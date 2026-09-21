# OpenClaw Watch — 2026-09-21

## What shipped

| Version | Date | Type | Headline |
|---------|------|------|----------|
| **2026.8.1** | ~Aug 2026 | Stable (2.0) | Full-stack rewrite: memory, skills, runtime, channels, security |
| **2026.9.1** | ~Sep 2026 | Stable | Mermaid diagrams, safer update recovery, lower long-conversation overhead |
| **2026.9.2** | ~Sep 2026 | Stable | Reliability/recovery improvements, GPT-6 Astra + Meta Muse Spark 1.3 support |
| **2026.9.3** | ~Sep 2026 | Stable | Live browser automation, repository-backed cloud work, persistent Workshop skills |
| **2026.9.4** | Sep 11, 2026 | Stable | Plugin/skill discovery, multi-query memory promotion, config read-only mode |
| **2026.9.5** | Sep 19, 2026 | Stable | Bounded device failover, versioned-state cleanup, multi-source queue deduplication |

Baseline was **2026.5.27** (stable) / **2026.5.28-beta.2** (beta). The landmark is **2026.8.1 = OpenClaw 2.0**, which touched every subsystem.

No beta newer than 2026.9.5 visible in the releases index as of 2026-09-21.

---

## What's notable

### 1. Background memory consolidation ("grounded dreaming") — 2026.8.1
Model-backed background job promotes provenance-qualified memories into long-term storage. Only scanner-approved or Workshop-owned material advances automatically; user-authored changes stay in `pending`. This separates the *recall path* from the *promotion path* — memory quality gates happen offline, not inline with a request.

### 2. Multi-query memory promotion heuristics — 2026.9.4
Long-term promotion now requires multiple *distinct recall queries*, not mere re-exposure or background scans. Configurable via `minUniqueQueries`. Prevents low-signal notes from inflating long-term memory. Directly addresses the noisy-memory problem in high-volume agents.

### 3. Bounded device failover with cleanup gate — 2026.9.5
Task placement tries at most **three** devices. Each failover waits for cleanup confirmation on the failed device before proceeding; workspace preparation acts as a hard retry cutoff. This is explicit capacity-aware placement rather than blind round-robin.

### 4. Versioned session-state cleanup — 2026.9.5
Old versions of session-list data were being held indefinitely in Gateway memory, causing exhaustion under load. Fix: explicit release of superseded version objects after each session refresh. A clean pattern for any in-process state store that accumulates diffs.

### 5. Config read-only mode via `OPENCLAW_CONFIG_READONLY=1` — 2026.9.4
Prevents the runtime from overwriting externally-managed config (e.g., deployed via secrets manager). Conversations and working data still require writes; only the config layer is frozen. Simple env-var gate, no API surface change.

---

## What we can use in Lexicon

Ranked by **value / effort** (H/M/L), mapped to real Lexicon source paths.

| # | Pattern | Value | Effort | Lexicon target |
|---|---------|-------|--------|----------------|
| 1 | **Multi-query memory promotion** — gate long-term writes behind N distinct recall hits instead of first-exposure | H | L | `src/engine/memory/manager.py` |
| 2 | **Bounded retry with cleanup confirmation** — cap orchestrator retries at 3, require cleanup ack before next attempt | H | L | `src/engine/orchestrator.py` |
| 3 | **Background memory consolidation job** — offline promotion pass, keeps inline request path fast | H | M | `src/engine/memory/manager.py` + `src/cron/scheduler.py` |
| 4 | **Work-queue durability across restarts** — distinguish "attempted" (deduplicate) vs. "queued" (mutable) messages | M | L | `src/engine/queue.py` |
| 5 | **Versioned-state cleanup** — release superseded in-memory versions after each session refresh | M | L | `src/gateway/session.py` |
| 6 | **Redacted command logging** — strip secret values from task labels, preserve distinctiveness | M | L | `src/shared/logger.py` |
| 7 | **Skill apply/reject/quarantine without extra prompts** — agent-initiated skill lifecycle in Workshop approvals | M | M | `src/engine/skills.py` |
| 8 | **Config read-only mode env var** — freeze config layer for externally-managed deployments | L | L | `src/shared/config.py` |

---

## Picks for the next spike

**Spike 1 — Multi-query memory promotion (`src/engine/memory/manager.py`)**  
Highest signal-to-noise win. Add a `min_unique_queries: int = 2` threshold to the promotion logic in `manager.py`. Currently the manager promotes after recall exposure; gating on a distinct-query count prevents one chatty session from polluting long-term memory. Low risk, isolated change.

**Spike 2 — Bounded retry in orchestrator (`src/engine/orchestrator.py`)**  
The orchestrator currently has no explicit retry ceiling. Adding `MAX_PLACEMENT_ATTEMPTS = 3` with a cleanup-confirmation await before each retry directly mirrors the OpenClaw pattern and prevents cascading worker exhaustion.

**Spike 3 — Offline consolidation cron (`src/cron/scheduler.py` + `src/engine/memory/manager.py`)**  
Register a low-priority scheduled job that runs `manager.consolidate()` — sweeping `pending` memories, scoring them, and promoting or discarding. Keeps the inline path fast and aligns with the heartbeat already in `src/cron/`.
