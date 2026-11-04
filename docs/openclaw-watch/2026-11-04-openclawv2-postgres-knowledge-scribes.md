# OpenClaw Watch — 2026-11-04

**Period covered:** 2026.5.27 (last-seen stable) → 2026.10.10 (current stable) · 2026.5.28-beta.2 → 2026.11.5-beta.1 (current beta)

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.8.1 | Aug 2026 | stable | "OpenClaw 2.0" — memory overhaul, session continuity, grounded dreaming |
| 2026.9.36 | ~Sep 2026 | stable | Patch series (9.1–9.36): runtime hardening, MCP fixes, cron recovery |
| 2026.10.9 | 29 Oct | stable | Workspace-only tool policy, credential masking in MCP, validate-before-mutate |
| 2026.10.10 | 03 Nov | stable (extended) | Gateway-focused extended-stable cut; 4,825 commits, 454 contributors |
| 2026.10.10-beta.2 | 19 Oct | beta | Multi-file patch validation, plugin hook enforcement across all entry points |
| 2026.10.10-beta.5 | 30 Oct | beta | Node version fixes, Gateway stream stall fix, cron missed-run recovery |
| 2026.11.5-beta.1 | 04 Nov | beta | Knowledge Scribes, PostgreSQL data layer, decision/media model routing, persistent cron streams |

---

## What's notable

### 1. Grounded Dreaming — provenance-aware background memory consolidation (2026.8.1)
Active Memory now runs model-backed background consolidation ("grounded dreaming") that promotes provenance-qualified material into long-term memory, logging each promotion in a Dream Diary. Memory ownership tooling tracks which sessions contributed to a memory item and allows targeted removal with `openclaw memory forget` without touching source transcripts. This is the most significant memory architecture shift in the codebase's history.

### 2. Knowledge Scribes — cross-agent reusable knowledge capture (2026.11.5-beta.1)
A new "scribes" abstraction captures knowledge during a session and makes it reusable across other agents and sessions from the Control UI. This sits above memory (a session-scoped scratchpad) and below skill (a durable automation) — a shareable, addressable knowledge unit.

### 3. PostgreSQL Data Layer with migration tooling (2026.11.5-beta.1)
State storage can now target PostgreSQL as an alternative backend, with schema migration tooling and compatibility coverage for in-place SQLite-to-Postgres migrations. This is the first first-class relational backend in OpenClaw's history.

### 4. Decision and media model routing (2026.11.5-beta.1)
Provider-aware routing now distinguishes decision tasks (small/fast model) from media tasks (multimodal model) from general tasks. ClawRouter integration formalizes the routing contract. Pairs with the 2026.8.1 change that added a provider-declared "small model" for short title/progress tasks.

### 5. Validate-before-mutate for multi-file patches (2026.10.9 / beta.2)
Before any file in a multi-file write is changed, all targets are validated. If any target is missing or its context doesn't match, the whole patch is rejected and the workspace stays intact. Plugin `before_tool_call` hooks now run consistently across all entry points (including `openclaw agent exec`), closing a bypass path.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified to exist under `src/`.

| Rank | Pattern | Value | Effort | Lexicon target |
|---|---|---|---|---|
| 1 | **Decision model routing** — route short/structural tasks to a small/fast model, multimodal tasks to a media model | High | Low | `src/engine/llm/router.py` |
| 2 | **Background memory consolidation** — periodic background job promotes episodic items to long-term memory with provenance tags | High | Medium | `src/engine/memory/episodic.py`, `src/engine/memory/manager.py` |
| 3 | **Knowledge Scribe pattern** — session-scoped knowledge capture that can be persisted and re-surfaced across sessions | High | Medium | `src/engine/memory/working.py`, `src/engine/skills.py` |
| 4 | **Validate-before-mutate for vault writes** — validate all write targets before mutating any | Medium | Low | `src/engine/tools/vault_write.py` |
| 5 | **PostgreSQL backend** — replace or augment SQLite-based cron/memory stores with Postgres | Medium | High | `src/cron/store.py`, `src/engine/memory/manager.py` |
| 6 | **External supervisor mode** — allow an external process to own Gateway restarts so the runtime doesn't self-restart mid-session | Medium | Medium | `src/gateway/server.py` |
| 7 | **Plugin hook enforcement at all entry points** — `before_tool_call` hooks run regardless of how a tool is invoked | Low | Low | `src/engine/hooks/registry.py`, `src/engine/hooks/loader.py` |

---

## My picks for what to spike next

**Spike 1 (this week): Decision model routing** → `src/engine/llm/router.py`
Lexicon already has a router and multiple providers (`claude_provider.py`, `openai_provider.py`, `litellm_provider.py`). Adding a lightweight routing tier — short/structural tasks to a declared "small" model, audio transcript tasks stay on the current path — is a small, high-signal change. No new dependencies.

**Spike 2 (next sprint): Background memory consolidation** → `src/engine/memory/episodic.py`
Lexicon has an episodic store and a cron scheduler (`src/cron/scheduler.py`). Wire a background cron job that calls a consolidation pass on `episodic.py`, scoring and promoting items to `manager.py`'s long-term store. The Dream Diary pattern (a provenance log per promotion) is worth adopting wholesale — it makes memory auditable.

**Watch (beta, not yet stable): Knowledge Scribes + PostgreSQL backend**
Both are in `2026.11.5-beta.1` only. Wait for stable cut before porting. The PostgreSQL backend in particular carries migration risk; track it but don't start until 2026.11.x stable.

---

*Sources: github.com/openclaw/openclaw/releases (primary), search results confirming v2026.10.10 as latest stable and v2026.11.5-beta.1 as latest beta. docs.openclaw.ai and releasebot.io are outside this session's allowed network domains.*
