# OpenClaw Watch — 2026-07-26

Baseline: stable 2026.5.27 · beta 2026.5.28-beta.2  
Reviewed: stable 2026.6.11, 2026.7.1 · beta 2026.7.2-beta.3

---

## What Shipped

### Stable 2026.6.11 — June 30, 2026
Reliability-focused release. Channel delivery hardened across 10+ platforms (Telegram, WhatsApp, Matrix, Discord, Slack). Memory/session continuity: conversations survive reconnects, long sessions retain prompt-cache savings across turns, compaction cancellation prevents context loss. Gateway readiness checks go unhealthy during restart drains. Security: plugin policies persist through registry changes; approval results return to originating channel/DM. Runtime: MCP request limits bounded to prevent resource exhaustion; model list caching reduces startup filesystem scans.

### Stable 2026.7.1 — July 13, 2026
Major feature release (3,063 commits, 532 contributors). Control UI fully redesigned around live tasks. Coding: `openclaw attach` enables temporary session bridging to Claude Code. Gateway cascade-failure prevention: repeatedly failing gateways now enter stable repair pathways instead of restart loops. Security hardening: tokens/secrets scrubbed from logs; approval scopes locked to authorized users; unsafe downloads/network requests blocked at intake. Model expansion: GPT-5.6, Tencent Hy3, Meta Muse Spark 1.1, broader Claude/Ollama support.

### Beta 2026.7.2-beta.3 — July 18, 2026
Architectural expansion. Remote execution model: cloud worker infrastructure for session placement, dispatch, and worker-turn routing. MCP session isolation: server connections scoped to requesting session. Skills compaction: all included skill identities preserved before prompt-budget trimming, with UTF-16-safe truncation. Cron lifecycle retry preservation across scheduled, manual, and startup-recovered runs. Cron history served from task ledger. Per-method rate limiting on control-plane ops (30 req/min). External gateway supervision mode (`OPENCLAW_SUPERVISOR_MODE=external`).

---

## What's Notable

### 1. MCP Session Isolation
`src/engine/registry.py` · `src/gateway/session.py`  
Connections from MCP servers are now scoped to the session that requested them, not shared globally. This prevents cross-session tool leakage and resource contention under concurrent users — a security and isolation win. Lexicon currently shares tool registries globally.

### 2. Gateway Cascade-Failure Prevention
`src/gateway/server.py`  
Gateways that fail repeatedly no longer loop on auto-restart. OpenClaw now tracks failure count and enters a "stable repair" state requiring operator intervention or health-check recovery. Prevents CPU-spinning restart loops in degraded environments.

### 3. Prompt-Cache Retention Across Compaction
`src/engine/context/compactor.py` · `src/engine/memory/working.py`  
Long sessions now hold onto prompt-cache savings across turns even through compaction. The pattern: compactor preserves a "cache anchor" in working memory so the LLM provider can resume from the cached prefix rather than re-ingesting the full context on every post-compaction turn.

### 4. Skills Compaction with Identity Preservation
`src/engine/skills.py`  
Before truncating skill descriptions to fit the prompt budget, OpenClaw records every skill's identity token. Truncation is then applied only to descriptions, never to names/IDs — ensuring skills remain discoverable even at tight context limits. Critical for Lexicon's growing skill registry.

### 5. Cron Lifecycle Retry Decisions Persisted
`src/cron/scheduler.py`  
Retry decisions made during a scheduled execution phase now survive across restart types (scheduled, manual trigger, startup recovery). This closes a gap where a job that decided "retry" could be forgotten if the process restarted mid-flight before the decision was committed.

---

## What We Can Use in Lexicon

Ranked by value/effort ratio (high-value first):

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---------|-------|--------|-----------------|
| 1 | **LLM fallback on usage-limit errors** | High | Low | `src/engine/llm/router.py` |
| 2 | **MCP session isolation** | High | Medium | `src/engine/registry.py`, `src/gateway/session.py` |
| 3 | **Gateway cascade-failure prevention** | High | Medium | `src/gateway/server.py` |
| 4 | **Skills compaction with identity preservation** | Medium | Low | `src/engine/skills.py` |
| 5 | **Cron retry decision persistence** | Medium | Low | `src/cron/scheduler.py`, `src/cron/store.py` |
| 6 | **Prompt-cache anchor across compaction** | Medium | Medium | `src/engine/context/compactor.py`, `src/engine/memory/working.py` |
| 7 | **Token/secret log scrubbing** | Medium | Low | `src/shared/logger.py` |

**Notes:**

- **#1 (LLM fallback):** `router.py` already routes across providers. Adding usage-limit error classification to trigger fallback selection is a single-case addition. Immediately improves resilience against rate-limit spikes.
- **#2 (MCP isolation):** Lexicon's `src/engine/tools/registry.py` is session-unaware. Scoping it to `src/gateway/session.py`'s session context would prevent tool bleed in multi-user deployments.
- **#3 (gateway repair state):** `src/gateway/server.py` does not appear to track restart count. Adding a failure threshold + backoff-to-degraded-state pattern directly addresses potential restart loops.
- **#4 (skills compaction):** `src/engine/skills.py` truncates or excludes skills at context limits. Preserving identities first ensures routing remains valid even when descriptions are shortened.
- **#7 (log scrubbing):** `src/shared/logger.py` — token/API key scrubbing is a quick defensive add; worth doing regardless of other work.

---

## My Picks for What to Spike Next

1. **LLM fallback on usage-limit errors** (`src/engine/llm/router.py`): Low-hanging, high-resilience. Classify `rate_limit`/`usage_limit` error codes from each provider and route to the next configured fallback. One-day spike.

2. **MCP session isolation** (`src/engine/registry.py` + `src/gateway/session.py`): The most architecturally significant pattern from this cycle. As Lexicon scales to multi-agent and multi-user use cases, globally-shared tool registries are a liability. Worth a design spike before implementation.

3. **Token/secret log scrubbing** (`src/shared/logger.py`): Quick win, do it before the next deployment. Audit log calls in `src/gateway/` and `src/engine/llm/` for any place secrets could reach structured logs.
