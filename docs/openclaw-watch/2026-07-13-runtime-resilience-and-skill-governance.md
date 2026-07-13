# OpenClaw Watch: 2026-07-13 — Runtime Resilience & Skill Governance

**Period covered:** 2026.5.27 (stable baseline) → 2026.6.9 (latest stable) / 2026.5.28-beta.2 → 2026.7.1-beta.6 (latest beta)

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.6.1 | Jun 3, 2026 | Stable | Resilient agent/Codex recovery; Skill Workshop with plugin contracts; SQLite migration for plugin indexes, cron, and channel state |
| 2026.6.5 | Jun 9, 2026 | Stable | Extended-thinking stream recovery; MCP non-text block normalization; cron JSON→SQLite auto-migration; parallel web search as first-class provider |
| 2026.6.8 | Jun 18, 2026 | Stable | Richer Telegram/WhatsApp channel delivery with HTML/markdown fidelity |
| 2026.6.9 | Jun 21, 2026 | Stable | Provider plugins as first-class npm releases with auto-discovery at startup; improved Codex integration; agent retry/compaction hardening; 422 PRs |
| 2026.7.1-beta.2 | Jul 5, 2026 | Beta | Initial 2026.7.1 beta — Claude Sonnet 5 + new model integrations |
| 2026.7.1-beta.5 | Jul 11, 2026 | Beta | Session auto-titling via utility-model routing; native macOS app |
| 2026.7.1-beta.6 | Jul 13, 2026 | Beta | Container migrations before Gateway readiness; safe mode on unclean boots; SecretRef credential protection; ClawRouter with dynamic model discovery |

---

## What's notable

**1. Skill Workshop / Plugin Contracts (2026.6.1)**
OpenClaw now ships a structured proposal-review workflow for skills: operators see disabled-skill snapshots, approve support files, and accept versioned plugin contracts with rollback. Skills are no longer implicitly trusted at load-time — approval gates are explicit. This is the clearest articulation we have seen of a runtime-enforced authorization model for skills.

**2. SQLite state migration for scheduling and channels (2026.6.1 / 2026.6.5)**
All mutable stores — cron jobs, plugin indexes, channel state — migrated from JSON files to SQLite. Auto-migration runs on startup before anything else touches state. This yields transactional writes, queryable history, and crash-safe updates to every periodic and channel operation without a separate database server.

**3. Extended-thinking stream recovery (2026.6.5)**
Anthropic extended-thinking sessions now survive process restarts: stream-continuation events are buffered until `message_start` is received before being forwarded to the turn accumulator. Without this guard, resumed streams double-emit partial thinking blocks, silently corrupting turn state and token counts.

**4. Resilient interrupted-tool-call recovery (2026.6.1 / 2026.6.9)**
The agent runner detects interrupted tool calls (crash-mid-call, stale session bindings, compaction handoffs) and reconciles turns to a known completed state rather than hanging or emitting orphaned tool-result blocks. Channel state — WhatsApp, iMessage, Discord — is separately preserved across restarts via the same recovery path.

**5. Container migrations before Gateway readiness + safe mode (2026.7.1-beta.6)**
Schema migrations now run as a mandatory blocking pre-flight before the Gateway marks itself healthy. On repeated unclean boots the system activates a safe mode instead of restart-flapping — preserving diagnostics and preventing cascading state corruption.

---

## What we can use in Lexicon

Ranked by value/effort, mapped to verified `src/` paths:

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---------|-------|--------|-----------------|
| 1 | Extended-thinking stream recovery — buffer continuation events until `message_start` before forwarding to turn accumulator | High | Low | `src/engine/llm/claude_provider.py` |
| 2 | SQLite migration for cron store — replace JSON file writes with transactional SQLite; auto-migrate on startup | High | Low | `src/cron/store.py` |
| 3 | Skill approval gates / plugin contracts — explicit load-time authorization checks for skills and tools | High | Medium | `src/engine/skills.py`, `src/engine/hooks/registry.py` |
| 4 | Interrupted-tool-call recovery — detect stale/orphaned tool calls and reconcile turns to completion | Medium | Medium | `src/engine/runner.py`, `src/engine/orchestrator.py` |
| 5 | Gateway pre-flight migrations + safe mode on repeated unclean boots | Medium | Medium | `src/gateway/server.py` |

---

## Picks for what to spike next

**Spike 1 (this week): Extended-thinking stream recovery in `src/engine/llm/claude_provider.py`.**
Highest signal-to-noise ratio. A focused change: buffer all streaming events until `message_start` is confirmed before passing them to the turn accumulator. Eliminates a class of silent corruption bugs in any Lexicon session using Claude extended thinking. Low blast radius; easily isolated in a feature flag.

**Spike 2 (next sprint): SQLite migration for `src/cron/store.py`.**
Lexicon's cron store persists state as JSON; concurrent writers and process crashes can corrupt it. OpenClaw's migration pattern is battle-tested across hundreds of PRs. Porting it unlocks reliable heartbeat-driven skills and makes `src/cron/scheduler.py` crash-safe by default.
