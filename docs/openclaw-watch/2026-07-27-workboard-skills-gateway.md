# OpenClaw Watch — 2026-07-27

**Stable:** 2026.7.1 (was 2026.5.27) · **Beta:** 2026.7.2-beta.3 (was 2026.5.28-beta.2)  
Three stable releases and a beta since last baseline. Themes: multi-agent coordination, skill governance, gateway hardening.

---

## What shipped

### 2026.6.1 — June 3, 2026
Multi-agent Workboard with SQLite-backed task state and workboard goals that survive reloads. Skill Workshop: pending proposals, rollback metadata, external package boundaries, and support-file approvals for operator governance. Operational resilience: interrupted tool calls, stale session bindings, and auth profile failovers now recover without data loss. MiniMax M3 model support; concurrent CLI metadata rendering.

### 2026.6.8 — June 16, 2026 (192 PRs, 200+ contributors)
Memory embedding batches now split before the 431-char provider limit. SQLite WAL disabled on network filesystems to prevent corruption. GLM-5.2 and Claude Haiku 4.5 model support added with normalized provider IDs. Web-search key-free providers (DuckDuckGo, Parallel Free, Ollama) made explicit opt-ins instead of silent fallbacks. Usage-footer rendering with credential-aware limits.

### 2026.7.1 — July 13, 2026 (3,063 commits, 532 contributors)
`openclaw attach` CLI lets Claude Code claim temporary session access without full auth re-negotiation — clean delegation-boundary pattern. Repeatedly failing gateways now surface a structured repair path instead of looping restarts. Full Control UI overhaul with live task board, usage/cost views, and Gateway health monitoring. Model expansion: GPT-5.6, Tencent Hy3, Meta Muse Spark 1.1.

### 2026.7.2-beta.3 — July 18, 2026 (current beta)
Remote coding sessions on cloud workers, paired-node coding agents, mobile Voice Wake on Android, Linux deb/AppImage packaging, iOS offline mode with pre-cached transcripts.

---

## What's notable

1. **Workboard task-backed multi-agent coordination** (2026.6.1): Tasks are first-class, SQLite-persisted objects that agents pick up even after crashes. The Chief no longer loses delegated work on restart; sub-agents resume from a board entry rather than starting blind.

2. **Skill governance via Workshop** (2026.6.1): New skills enter a pending-proposal queue for operator review before activation. Rollback metadata and external package boundaries prevent uncontrolled skill sprawl in production deployments.

3. **Memory embedding batch splitting** (2026.6.8): Embedding API calls are now pre-split before hitting provider size limits. Simple guard, but it makes episodic/short-term indexing robust against silent 400 errors on larger content chunks.

4. **Gateway repair paths instead of restart loops** (2026.7.1): A gateway that fails repeatedly stops restarting silently and instead surfaces a structured repair flow. Exposes a circuit-breaker + error-surface pattern directly applicable to WebSocket session management.

5. **`openclaw attach` session delegation** (2026.7.1): Shows a clean "external agent joins live session" boundary — temporary credential grant, scoped access, no full re-auth. Informative for how Lexicon might let tools or external processes hand off to a running runtime.

---

## What we can use in Lexicon

| # | Pattern | Value | Effort | Lexicon target |
|---|---------|:-----:|:------:|---------------|
| 1 | Workboard / task-backed sub-agent coordination | High | Medium | `src/engine/orchestrator.py` |
| 2 | Skill governance — pending proposals + rollback | High | Medium | `src/engine/skills.py` |
| 3 | Memory embedding batch splitting | Medium | Low | `src/engine/memory/search.py` |
| 4 | Gateway restart-loop protection / circuit breaker | Medium | Low | `src/gateway/server.py` |
| 5 | LLM provider ID normalization | Low | Low | `src/engine/llm/router.py` |

---

### 1 · Workboard / task-backed sub-agent coordination → `src/engine/orchestrator.py`

`Orchestrator._active_runs` (line 71) is an in-process `set[str]` that evaporates on crash. Sub-agents are ONESHOT by design (doc at line 14), meaning any delegation in flight when the process restarts is silently dropped. OpenClaw's Workboard makes tasks first-class, durable entries.

Concretely: extend `Orchestrator` to write a lightweight task record to `src/cron/store.py` (already a JSON-backed store) when a sub-agent run starts and mark it complete or failed when it finishes. On startup, the orchestrator can surface interrupted runs for the Chief to decide whether to retry. The `MAX_CONCURRENT_SUBAGENTS` guard (line 43) stays but now counts persisted-running rather than in-memory runs.

### 2 · Skill governance — pending proposals + rollback → `src/engine/skills.py`

`SkillRegistry.load_all()` (line 112) applies the three-tier scan immediately, with no review gate. A new SKILL.md in Tier 2/3 is live on next hot-reload (`_watch_loop`, line 244). One malformed or unreviewed skill can silently degrade a live persona.

OpenClaw's Workshop queues incoming skill changes as proposals; operators review and approve via CLI or Gateway endpoint. For Lexicon: add a `pending` state to `SkillDefinition`, intercept new/changed skills in `_watch_loop`, write them to a `pending_skills.json` sidecar, and expose a `/cron/skills/approve` endpoint in `src/gateway/server.py`. Approved skills apply immediately; rejected ones write rollback metadata. Zero change to the existing three-tier index.

### 3 · Memory embedding batch splitting → `src/engine/memory/search.py`

`MemoryManager.recall()` (line 97 in `src/engine/memory/manager.py`) passes chunks directly to `src/engine/memory/search.py` for MMR re-ranking, which may call the vector provider. Neither path guards batch size. OpenClaw 2026.6.8 fixed this with a pre-split before the embed call.

The fix is a two-step chunk → split-at-limit → embed loop in `src/engine/memory/search.py` before any batched vector call. With `MAX_CONTEXT_CHARS = 4000` and content sliced to 500 chars each (line 130 in manager.py), individual chunks are safe, but a future batch indexing path (short-term or episodic bulk insert) won't be.

### 4 · Gateway restart-loop protection → `src/gateway/server.py`

The `websocket_endpoint` handler at line 170 catches `WebSocketDisconnect` (line 326) and `Exception` (line 328), then always cleans up via `finally:`. There is no counter on repeated fast reconnects from the same client; a misbehaving client can oscillate and create/destroy sessions in a tight loop.

Port OpenClaw's pattern: track per-IP or per-session consecutive-failure count in `SessionManager`, apply exponential backoff after N (e.g. 3) fast failures within a window, and surface a structured error via `ErrorMessage(code="gateway_repair")` rather than silently dropping. The `finally:` block at line 330 is the right insertion point.

### 5 · LLM provider ID normalization → `src/engine/llm/router.py`

OpenClaw 2026.6.8 normalized provider IDs across config and registry to prevent routing mismatches. Lexicon's `PersonaLLMRouter` is small enough that mismatches are unlikely now, but noting it here for when provider count grows.

---

## My picks for what to spike next

**Immediate spike — Skill governance (2):** The hot-reload watcher activates skills with zero review. One unvetted SKILL.md silently degrades a live persona. A pending-proposal layer in `src/engine/skills.py` + a gateway approval endpoint is the highest-impact, lowest-risk change. The watcher hook is already in place; the proposal queue is an additive layer.

**Close second — Workboard coordination (1):** As Lexicon adds personas, ONESHOT drops on crash become a production pain point. The `src/cron/store.py` store is already in place; extending it to hold sub-agent task records is the structural fix, and the `_active_runs` set at `src/engine/orchestrator.py:71` shows exactly where the durable record would replace the in-memory sentinel.
