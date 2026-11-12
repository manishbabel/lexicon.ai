# OpenClaw Watch: November 2026 Releases

**Date:** 2026-11-12  
**Last checked:** 2026-09-23  
**New stable:** 2026.11.1 → 2026.11.3  
**New beta:** 2026.11.5-beta.2

---

## What Shipped

| Version | Date | Type | Headline |
|---------|------|------|----------|
| 2026.10.9 | Oct (details not retrieved) | stable | — |
| 2026.10.10 | Oct (details not retrieved) | stable | — |
| 2026.9.37 | 10 Nov | extended-stable | Late-Sep code + critical security/reliability patches on retired maintenance line |
| 2026.11.1 | 05 Nov | stable | 78 PRs: channel reliability, scheduler fixes, prompt-cache stability, subagent authority |
| 2026.11.2 | 08 Nov | stable | 166 commits, 113 PRs — full notes external |
| **2026.11.3** | **10 Nov** | **latest stable** | Security hardening: credential scoping, secret isolation, cron resilience |
| 2026.11.5-beta.1 | ~11 Nov | beta | — |
| **2026.11.5-beta.2** | **12 Nov** | **latest beta** | Scheduler startup ordering, memory race fixes, URI rejection hardening |

---

## What's Notable

### 1. Cron/Scheduler Resilience Trilogy
Across three releases, OpenClaw hardened its scheduler against failure modes that cause silent data loss or stuck startups:
- **2026.11.3:** Cron storage failures no longer exit the Gateway — previously a failed DB write could crash the whole process.
- **2026.11.1:** Interrupted long jobs no longer block scheduler startup. Canceled cron runs now stop their reply hooks.
- **2026.11.5-beta.2:** Jobs added *before* the scheduler starts run without an extra delay. Startup evidence is flushed before readiness is declared.

### 2. Secret Isolation for Spawned Processes
**2026.11.3** introduced a consistent pattern: child processes do not inherit parent secrets.
- Managed Signal daemons and bundled language servers no longer inherit Gateway secrets.
- Inline environment credentials are redacted from config reads.
- Plugin results are scoped to their connection credentials — a plugin cannot read another plugin's auth context.

### 3. Prompt-Cache Stability
**2026.11.1** fixed a subtle cache-miss amplifier: session tool definitions were mutating between turns, causing unnecessary cache busts. The fix: tool definitions are stabilized (deduplicated/canonicalized) before the LLM call so the cache key stays consistent.

### 4. Memory Indexing Sequencing
**2026.11.1 + 2026.11.5-beta.2** addressed ordering races in memory:
- Memory indexing now waits for archived transcript materialization rather than racing against it.
- Workspace memory and skill imports no longer race on first turns when plugins load from source.

### 5. Input Rejection at Boundaries
**2026.11.5-beta.2** standardized early rejection of bad inputs:
- Malformed URI identifiers rejected via fast-uri 4.2.3 before they reach routing.
- Oversized bounded collections rejected at the ingestion boundary (Discord SDK + Zod parser) rather than deep in processing.

---

## What We Can Use in Lexicon

Ranked by value/effort (high value first).

### #1 — Cron store errors must not crash the scheduler  
**Value: High | Effort: Low**  
`src/cron/scheduler.py` and `src/cron/store.py`  
Currently, an exception from the store (DB write, serialization error) propagates up and can terminate the scheduler loop. Wrap the store calls in `scheduler.py` with try/except that logs and skips rather than re-raises, mirroring OpenClaw's fix in 2026.11.3.

### #2 — Gateway session must not leak env secrets to subprocesses  
**Value: High | Effort: Low–Medium**  
`src/gateway/server.py` and `src/shared/config.py`  
Any subprocess Lexicon forks (MCP servers, tool wrappers) will inherit the full `os.environ`. Add a `scrub_env()` helper in `src/shared/config.py` that strips known secret keys before `subprocess.Popen`, and call it from `src/gateway/server.py` wherever child processes are spawned.

### #3 — Stabilize tool definitions between turns to avoid prompt-cache misses  
**Value: High | Effort: Medium**  
`src/engine/llm/claude_provider.py` and `src/engine/runner.py`  
If the tool list passed to the Anthropic API changes order or gains ephemeral fields between turns, the prompt cache busts every turn. Canonicalize (sort by name, strip runtime-only metadata) the tools list in `claude_provider.py` before building the request, so the cache key is stable.

### #4 — Transcript indexing must sequence after archival completes  
**Value: Medium | Effort: Medium**  
`src/engine/memory/transcript_index.py` and `src/engine/memory/manager.py`  
If `manager.py` triggers indexing concurrently with transcript archival, the index can capture an incomplete snapshot. Add an explicit await/event between archival completion and index rebuild in `manager.py`.

### #5 — Reject malformed tool inputs at gateway boundary  
**Value: Medium | Effort: Low**  
`src/gateway/protocol.py` and `src/engine/tools/registry.py`  
Add size bounds and URI validation on incoming tool call arguments in `protocol.py` before they reach the engine, rather than letting individual tools discover bad inputs deep in execution.

---

## My Picks for Next Spike

**Spike 1 (this week):** `src/cron/scheduler.py` cron-store error isolation — highest bang for buck, contained change, directly prevents silent cron death.

**Spike 2 (next):** `src/engine/llm/claude_provider.py` tool-definition canonicalization — Lexicon uses Claude as primary LLM; every cache miss on a tools-heavy session doubles cost. Quick win.

**Spike 3 (after):** `src/gateway/server.py` env-secret scrubbing — worth auditing what's actually forked from gateway and adding the scrub helper.
