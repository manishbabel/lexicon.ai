# OpenClaw Watch — 2026-09-18

**Covering:** v2026.6.35 · v2026.7.33 · v2026.8.1 (2.0) · v2026.9.4  
**Baseline:** 2026.5.27 stable / 2026.5.28-beta.2  
**Checked:** 2026-09-18

---

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.6.35 | 2026-09-10 | Extended Stable (LTS final) | Safer provider/channel boundaries; reliable long-running delivery; bundled-plugin resilience |
| 2026.7.33 | 2026-09-18 | Extended Stable | Security + credential safety; UTF-16 boundary preservation; gateway/channel delivery hardening |
| 2026.8.1 | 2026-08-31 | Stable (2.0) | "Grounded dreaming" background memory consolidation; CPU-scaled concurrency; cloud sessions; skills workshop |
| 2026.9.4 | 2026-09-11 | Stable (latest) | Stability and bug-fix release across 1,558 PRs; no new architecture patterns |

Pre-release track since baseline: v2026.8.1-beta.3 → beta.4 → v2026.9.1 → 9.2 → 9.3 → 9.4 (stable).

---

## What's Notable

### 1. UTF-16 Boundary Safety in Context Pruning (v2026.7.33)
OpenClaw centralised two utilities — `truncateUtf16Safe` and `sliceUtf16Safe` — deployed across 50+ code paths spanning agents, channels, memory, and compaction. The key insight: naive char-count slicing splits Unicode surrogate pairs, corrupting messages mid-codepoint. The fix is a single authoritative helper that checks for a high surrogate at the cut point and backs up by one.

### 2. Bounded Concurrency on Session Discovery and Provider Requests (v2026.7.33)
Catalog feeds, history queries, provider requests, and parallel tool execution now carry explicit per-operation concurrency and size limits. "Expensive all-agent session discovery now bounded." The pattern: each fan-out path (not just the aggregate queue) carries its own limit, preventing a large agent roster from starving other work.

### 3. Credential and PII Redaction in Diagnostic Logs (v2026.7.33)
Diagnostic logs now redact synthetic credentials, webhook tokens, and phone numbers via per-subsystem loggers rather than a single global filter. Pattern: every subsystem registers its own sensitive-field list; a shared formatter applies redaction before the record reaches any handler.

### 4. Grounded Dreaming — Background Memory Consolidation (v2026.8.1)
"Grounded dreaming" enables model-backed background consolidation by default. While the agent is idle the runtime replays recent episodic events through a lightweight LLM call, extracts durable lessons, and writes them back — keeping human-authored memory edits as pending-review rather than overwriting them. This is separate from explicit recall; it runs on a cron cadence without user prompting.

### 5. CPU-Scaled Foreground Concurrency + External Supervisor Mode (v2026.8.1)
The Gateway now queries available parallelism at startup and sets an 8–16 slot concurrency ceiling accordingly. Separately, an external supervisor mode lets a process outside the Gateway own restart decisions, enabling clean reload without the Gateway self-managing its own lifecycle — important for process supervisors like systemd or container orchestrators.

---

## What We Can Use in Lexicon

Ranked by (value × ease):

### ① Credential redaction in logger — `src/shared/logger.py`  
**Value: HIGH / Effort: LOW**  
`setup_logger` in `src/shared/logger.py` emits records with no sensitive-field filtering. A `SensitiveFormatter` wrapper that masks known patterns (API keys, tokens, bearer headers) before any handler writes the record eliminates a silent data-leak risk. Single-file change, zero interface breakage.

### ② UTF-16–safe truncation in context pruner — `src/engine/context/pruner.py`  
**Value: MEDIUM / Effort: LOW**  
`_trim_text` at line 197 and `_soft_trim_message` at line 150 both use `len(text)` and raw slice notation, which splits surrogate pairs for non-BMP content (emoji, CJK extension blocks). Replacing the slice with a `_safe_slice(text, n)` helper that backs up one character when it lands on a high surrogate costs ~10 lines and protects every pruning stage.

### ③ Per-operation concurrency limit on orchestrator — `src/engine/orchestrator.py`  
**Value: HIGH / Effort: LOW–MEDIUM**  
`Orchestrator._run_subagent` at line 309 and `active_run_count` at line 343 exist, but there is no enforced ceiling before `_run_subagent` is called. Adding a semaphore (or a simple counter check against a config-driven `max_concurrent_agents` value) at the `route_to_agent` call site prevents agent-roster fan-out from exhausting the event loop. Affects `src/engine/orchestrator.py` only.

### ④ Grounded dreaming in memory manager — `src/engine/memory/manager.py` + `src/cron/scheduler.py`  
**Value: HIGH / Effort: MEDIUM**  
`_summarize_interaction` at line 332 already calls an LLM to compress episodes. The missing piece is a cron-triggered background pass that replays recent `store_episodic` entries through that summariser and promotes durable patterns into `store_note`, without overwriting user-authored notes. Wire a new `CronJob` in `src/cron/scheduler.py` pointing at a new `MemoryManager.consolidate()` method. Keeps human edits pending-review by checking a `user_authored` flag before overwriting.

### ⑤ Shutdown settlement semantics in gateway — `src/gateway/server.py`  
**Value: MEDIUM / Effort: MEDIUM**  
OpenClaw's pattern: work settles (drains in-flight requests) before the server signals completion; channels stop during reload; a failed account stop does not stall sibling teardown. `src/gateway/server.py` handles the session lifecycle but likely has no explicit drain-then-close ordering on `stop()`. Adding a `asyncio.wait_for(self._drain(), timeout=…)` before closing the socket matches the pattern with minimal disruption.

---

## My Picks — Spike These Next

1. **① Credential redaction** — one afternoon, high security value, no design discussion needed. Do it now.
2. **④ Grounded dreaming** — highest architectural value for Lexicon's differentiator (proactive memory). Start with a `consolidate()` stub in `src/engine/memory/manager.py` wired to a disabled-by-default cron job in `src/cron/scheduler.py`. Ship behind a feature flag.
3. **② UTF-16 pruner safety** — good cleanup PR, blocks no one, prevents rare but hard-to-debug corruption.
