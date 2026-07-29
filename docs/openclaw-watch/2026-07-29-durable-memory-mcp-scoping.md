# OpenClaw Watch — 2026-07-29

**Digest covers:** stable `2026.7.1` and beta `2026.7.2-beta.5`  
**Baseline:** stable `2026.5.27` / beta `2026.5.28-beta.2`  
**Sources:** [GitHub releases](https://github.com/openclaw/openclaw/releases) (primary); releasebot.io and docs.openclaw.ai both 403'd.

---

## What shipped

### `2026.7.1` — Stable (promoted npm `latest` July 13 UTC)
3,063 contributions from 532 contributors. Key headline areas:

- **Control UI overhaul** — conversation management, live task sidebar, cost/usage views, gateway health inline.
- **Model expansion** — GPT-5.6, Tencent Hy3, Meta Muse Spark 1.1 added to provider roster.
- **Coding agents** — Codex delegation and native subagents return tracked results more reliably; long-running sessions easier to resume.
- **Channel improvements** — Telegram, Slack, Discord, Apple Messages all received substantial updates.
- **Gateway crash loop recovery** — improved restart admission guarding.

### `2026.7.2-beta.5` — Beta (July 28, 2026)
- **Crash-durable state** via quarantine stores and crash-recoverable SQLite WAL snapshots.
- **Durable channel delivery** across Telegram, Signal, Slack, QQBot, IRC, Twitch, Tlon, Zalo with at-least-once guarantees.
- **Session rewind and branching** across web and native apps.
- **Dynamic job cadence and durable schedule-source streaming** — cron jobs adjust frequency and stream results durably.
- **Fast active-memory recall with cross-conversation defaults** — persistent recall that survives conversation boundaries.
- **MCP server connection scoping per session** — tool connections isolated per conversation.
- **Structured approvals with push notifications** — gated actions with cross-platform push.
- Local llama.cpp GGUF inference and Baseten Model API.

Notable fixes: SQLite maintenance race + live-WAL verification; one-shot cron job enablement through lifecycle races; CJK text compaction estimation; Codex exhaustion prevention; `Retry-After` header honoring for Anthropic API.

---

## What's notable

### 1. Crash-durable memory snapshots (WAL quarantine pattern)
OpenClaw introduced quarantine stores and crash-recoverable SQLite WAL snapshots for persisted agent state. On crash, partially-written memory is moved to a quarantine partition rather than corrupting the live store. On restart, the engine replays the WAL to the last verified checkpoint. This is a meaningful reliability upgrade over checkpoint-on-exit approaches.

### 2. Dynamic job cadence with durable schedule streaming
The cron subsystem gained backpressure-aware scheduling: job interval is dynamically widened under load and compressed during idle. Schedule-source state is now streamed durably so in-flight work at crash time is preserved in the ledger, not dropped. The `one-shot cron enablement through lifecycle races` fix reveals this was previously a silent failure mode.

### 3. Fast active-memory recall with cross-conversation defaults
Memory recall now uses an indexed hot-path that bypasses full embedding search for frequently accessed memories, with configurable defaults that persist across conversation boundaries. The pattern decouples recall latency from corpus size for the common case.

### 4. MCP server connection scoping per session
Previously, MCP connections in OpenClaw were global (shared across sessions). This release scopes each MCP server connection to an individual session, preventing tool state bleed between concurrent agents and enabling per-session capability grants. The `plugin install provenance warnings` complement this — installations now require explicit acknowledgement.

### 5. Gateway restart admission guard
`2026.7.1` hardened the gateway against crash loops by adding restart admission validation: a gateway that fails health checks post-restart is quarantined before it can accept new sessions, with supervisor escalation after N failed cycles. This decouples gateway liveness from session liveness.

---

## What we can use in Lexicon

Ranked by value/effort ratio (high value first within effort tier):

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---------|-------|--------|-----------------|
| 1 | **Fast active-memory recall** — hot-path index for frequent memories, cross-session defaults | High | Medium | `src/engine/memory/search.py`, `src/engine/memory/working.py` |
| 2 | **MCP scoping per session** — isolate tool registry to session context, not global | High | Medium | `src/engine/tools/registry.py`, `src/engine/skills.py` |
| 3 | **Dynamic job cadence** — widen cron interval under load, compress at idle | Medium | Low | `src/cron/scheduler.py` |
| 4 | **Crash-durable memory snapshots** — WAL quarantine on `manager.py` writes | High | High | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py` |
| 5 | **Gateway restart admission guard** — quarantine failing gateway before session admit | Medium | Medium | `src/gateway/server.py`, `src/gateway/router.py` |

**Not worth porting now:**
- Session rewind/branching — high complexity, no clear agent use case in current workspaces.
- Local GGUF inference — we route through `src/engine/llm/litellm_provider.py` which already handles this.
- Durable channel delivery — Lexicon's channel surface (`src/gateway/session.py`, `src/gateway/protocol.py`) is narrower; at-least-once semantics would require significant protocol changes.

---

## Picks for what to spike next

**Spike 1 — Fast active-memory recall** (`src/engine/memory/search.py`)  
Current `search.py` runs full embedding lookup on every recall. A recency-weighted in-memory index over the last N accessed memories, populated from `src/engine/memory/working.py` entries, would cut latency significantly for the typical turn-by-turn case. OpenClaw's approach (from beta.5 notes) suggests this is complementary to, not a replacement for, full search.

**Spike 2 — MCP scoping per session** (`src/engine/tools/registry.py`)  
The tools registry currently appears to be loaded once globally. Changing `registry.py` to accept a session context and gate capability grants per session would prevent the `ai-educator` and `software-engineer` workspaces from interfering with each other's tool state during concurrent use. Low risk: session context can be optional and default to the global registry for backward compat.
