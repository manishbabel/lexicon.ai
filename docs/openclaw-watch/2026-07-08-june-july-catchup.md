# OpenClaw Watch — 2026-07-08: June / July Catch-up

Covers the gap from baseline (2026.5.27 stable / 2026.5.28-beta.2 beta) through the current builds.

---

## What Shipped

| Version | Type | Date | Headline |
|---|---|---|---|
| 2026.6.1 | stable | Jun 1 | SQLite persistence expansion; Skill Workshop; plugin isolation |
| 2026.6.5 | stable | Jun 5 | Cron store SQLite migration; MCP result normalization; memory rerank toggle |
| 2026.6.6 | stable | Jun 6 | Channel delivery fixes; provider catalog stabilisation |
| 2026.6.9 | stable | Jun 9 | Minor fixes |
| 2026.6.10 | stable | Jun ~27 | Minor fixes |
| **2026.6.11** | **stable** | **Jun 30** | **Compaction instruction-retention; memory search timeout cancellation; gateway readiness drain; Slack relay router** |
| 2026.7.1-beta.1 | beta | Jul 2 | Native app modernisation, messaging capabilities |
| **2026.7.1-beta.2** | **beta** | **Jul 5** | **ClawRouter dynamic model discovery; on-exit schedule type; capability profiles; GPT-5.6 support** |

---

## What's Notable

### 1. SQLite-First Persistence (2026.6.1, 2026.6.5)

OpenClaw systematically replaced JSON/filesystem stores with SQLite across cron jobs, inbound queues, plugin install indexes, Discord thread bindings, iMessage monitor state, and the sandbox registry. The pattern reduces filesystem scan overhead on startup, enables atomic writes, and gives auto-migration hooks so schema changes don't leave stores in a broken state.

### 2. on-exit Schedule Type (2026.7.1-beta.2)

A new `on-exit` schedule keyword wakes an agent when a watched command/process exits rather than on a fixed timer. This is a conceptual shift from pure polling to hybrid event+timer scheduling: the cron layer now understands process lifecycles, not just wall-clock intervals. `session-targeted runs` also detach cleanly so heartbeat agents don't accumulate dangling sessions.

### 3. ClawRouter Bundled Provider Plugin (2026.7.1-beta.2)

A new `ClawRouter` provider plugin ships bundled with: credential-scoped dynamic model discovery, support for both OpenAI-compatible and native Anthropic/Gemini transports, and managed budget reporting. The key pattern is separating "what models are available right now" (dynamic catalog) from "how to route to them" (transport selection) — both can be extended via plugin without touching core router logic.

### 4. Compaction Preserves Repeated Instructions (2026.6.11)

OpenClaw's compactor was dropping recurring system-level instructions (persona rules, tool policies, formatting directives) because they matched the "repeated content" heuristic. The fix categorises instruction-tier messages separately from conversational content so they survive summarisation. Also: saved summaries now exclude raw token blocks and stale markers, and the compactor correctly handles oversized tool-heavy sessions.

### 5. MCP Result Normalization (2026.6.5)

Non-text blocks returned by MCP tools (images, audio, binary) are coerced to a text representation before being appended to conversation history. Without this, a follow-up turn that includes the raw block triggers an Anthropic 400 error because non-text content can't appear in certain message roles. The fix is small and defensive — normalise at the tool-call boundary, not at every downstream consumer.

---

## What We Can Use in Lexicon

Ranked by value/effort. Every path verified in `src/`.

### 1. Migrate cron store from JSON to SQLite — HIGH value / LOW effort
**File:** `src/cron/store.py`

`store.py` stores all cron definitions and runtime state in a single `jobs.json`. This is exactly the pattern OpenClaw replaced. Moving to SQLite gives: atomic writes (no corrupt-on-crash half-writes), schema migration via `ALTER TABLE`, and faster `store.list()` without loading the full JSON blob. The model is already a Pydantic `BaseModel` — mapping to an SQLite-backed store is a thin refactor. Pair with an auto-migration that promotes the existing `jobs.json` on first run.

### 2. Cancel background work on memory search timeout — HIGH value / LOW effort
**File:** `src/engine/memory/search.py`

`MemorySearcher` blocks on QMD embed/search calls without a timeout budget. When a search stalls (QMD slow, network hiccup) it holds the call open indefinitely. OpenClaw's fix: pass a deadline to the search call and, on timeout, cancel background embedding work rather than letting it accumulate. Add an `asyncio.wait_for` wrapper around the QMD call in `search.py` with a configurable timeout from config, and return a partial result or empty list so the agent can still respond.

### 3. Normalise non-text MCP results at the tool boundary — HIGH value / LOW effort
**File:** `src/engine/tools/registry.py`

When a registered tool returns a non-text content block (e.g. a binary blob, image reference, or compound MCP object), it should be serialised to a string representation before entering the message history. Without this, a subsequent LLM turn that replays the history hits an Anthropic 400. The fix belongs in `ToolDef` dispatch inside `registry.py`: after `handler()` returns, check the type and coerce non-string results to their string/JSON representation before returning to the runtime.

### 4. Protect repeated instructions through compaction — HIGH value / MEDIUM effort
**File:** `src/engine/context/compactor.py`

The current compactor summarises old messages into a digest. If system-level instructions (workspace SOUL, IDENTITY, skill preamble) appear repeatedly in history they can be collapsed into the digest or dropped entirely. Port OpenClaw's fix: classify messages before compaction — instruction-tier messages are preserved verbatim, conversational content is summarised. The compactor already strips tool result details before LLM calls; add the same categorisation step for instruction-tier content.

### 5. LLM router: re-probe primary after cooldown — MEDIUM value / LOW effort
**File:** `src/engine/llm/router.py`

When the primary LLM provider fails and the router falls back, it currently stays on the fallback until the process restarts. OpenClaw's fix: after `COOLDOWN_SECS`, re-probe the primary with a cheap health-check call and restore it if it responds. Add a `last_failed_at` timestamp to the provider state in `router.py` and promote the primary back on the next routing decision after the cooldown window expires.

### 6. on-exit schedule type in cron — MEDIUM value / MEDIUM effort
**File:** `src/cron/scheduler.py`

`scheduler.py` runs jobs on fixed time intervals via APScheduler. An `on-exit` trigger type would allow jobs to fire when a watched process (e.g. a long-running skill, an external CLI command) exits. Port as a new `TriggerType.ON_EXIT` in the cron model, with a lightweight watcher that polls a PID or subprocess handle and fires the cron job on completion. Lower-effort variant: add a `post_run_hook` field to `CronJob` that fires when a sibling job finishes.

### 7. Capability profiles — MEDIUM value / HIGH effort
**File:** `src/engine/context/` (new `profiles.py`)

OpenClaw introduced per-conversation scoped tool and access boundaries without weakening global defaults. For Lexicon this maps naturally onto the workspace model: each workspace already has a `SOUL.md` / `IDENTITY.md` defining persona; a `profiles.py` layer could enforce that a workspace's tools are scoped to only those listed in its `AGENT.md`, preventing cross-workspace tool bleed during multi-agent runs via `src/engine/tools/route_to_agent.py`.

---

## My Picks: Spike Next

1. **`src/cron/store.py` → SQLite** — Self-contained, zero API surface change, directly improves reliability of the cron subsystem that powers scheduled agent runs. Estimated: half a day.

2. **`src/engine/tools/registry.py` → MCP result normalisation** — Defensive one-liner class of fix. Prevents a silent failure mode (Anthropic 400 on replayed history) that's hard to debug and easy to prevent at the right boundary.

3. **`src/engine/memory/search.py` → search timeout + cancellation** — Long sessions will hit QMD latency. Capping search time keeps the agent responsive and prevents resource leaks in `src/engine/memory/manager.py` downstream.
