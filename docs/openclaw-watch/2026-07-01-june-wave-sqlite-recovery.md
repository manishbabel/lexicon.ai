# OpenClaw Watch — 2026-07-01

**Stable:** 2026.6.11 (June 30, 2026)
**Beta:** 2026.6.11-beta.2 (June 28, 2026)
**Baseline cleared:** 2026.5.27 stable / 2026.5.28-beta.2 beta

---

## What Shipped

Six stable releases since baseline (2026.6.1 → 2026.6.11), plus matching beta trains. Headline theme: **durability through SQLite everywhere + agent turn resilience**.

| Version | Date | Headline |
|---|---|---|
| 2026.6.1 | Jun 3 | SQLite for cron, channels, plugin index; skills governance; multi-agent workboard |
| 2026.6.5 | Jun 9 | Auth + session metadata to SQLite; memory-core to SQLite; MCP content normalization; ClawHub GitHub skill pins |
| 2026.6.6 | Jun 12 | Fail-closed security across tool/MCP/sandbox; compaction timeout 900→180s; embedding batching; model catalog cache |
| 2026.6.8 | Jun 16 | Oversized embedding batch splitting; SQLite WAL-off on NFS; invalid tool schema quarantine; key-free search opt-in hardening |
| 2026.6.9 | Jun 21 | External provider packages as first-class installs; agent run retries + history repair; Codex plugin auto-approval; Hosted Search |
| 2026.6.11 | Jun 30 | Per-contact model overrides; plugin catalog verification; provider stall auto-retry; Matrix E2EE memory leak fix |

---

## What's Notable

### 1. SQLite as the single durable store (2026.6.1 + 2026.6.5)
Cron run-logs, plugin install index, inbound channel queues, auth profiles, session metadata, memory-core dreams, and sandbox registry all moved from JSON files to SQLite in a two-release sweep. Migration runs at preflight with rollback safety. WAL mode is explicitly disabled on NFS mounts (2026.6.8) to prevent corruption.

### 2. Fail-closed tool and MCP boundaries (2026.6.6 + 2026.6.8)
Timed-out or unreadable tool schemas are now quarantined rather than silently broadening the allowed-tool set. The pattern: any approval or schema-parse failure defaults to `deny` rather than `allow`. Non-text MCP result blocks (resource links, audio, malformed images) are converted to text before hitting the provider, preventing broken conversation history (2026.6.5).

### 3. Agent turn resilience: interrupt recovery + compaction timeout reduction (2026.6.1 + 2026.6.6 + 2026.6.9)
Interrupted tool calls, stale session bindings, and compaction handoffs no longer strand work. Default turn timeout dropped 5× (900s → 180s) while honoring explicit overrides. Recurring cron jobs retry after transient model rate-limit errors rather than permanently failing.

### 4. Per-contact model routing (2026.6.11)
Different models can now be assigned to individual DM contacts across channels while preserving group/wildcard defaults. Provider-qualified model IDs honor per-agent runtime policies; oversized model catalogs are rejected before memory exhaustion.

### 5. External provider + skill packages as first-class installs (2026.6.9)
Provider plugins are now standard npm packages installable from ClawHub or GitHub with pinned commit SHAs and install telemetry. Plugin boundary isolation prevents cascade failures. Key-free search providers remain explicit opt-ins rather than silent fallbacks.

---

## What We Can Use in Lexicon

Ranked by value / effort. Each target verified to exist in `src/`.

### 1. SQLite cron persistence — `src/cron/store.py`
**Value: High / Effort: Low-Medium**
Lexicon's cron store (`src/cron/store.py`) is the natural first target. OpenClaw's pattern: migrate at preflight, keep legacy run-log table schema compatible, atomic writes only. A JSON-backed store risks corruption on kill mid-write; SQLite gives `BEGIN IMMEDIATE` atomicity for free. Also touches `src/cron/scheduler.py` for retry-after-rate-limit logic.

### 2. Fail-closed MCP/tool result normalization — `src/engine/tools/registry.py`
**Value: High / Effort: Low**
Lexicon's `src/engine/tools/registry.py` dispatches tool calls and collects results. Apply OpenClaw's two-part pattern: (a) normalize any non-text result block to a text representation before passing to the LLM provider (prevents provider API errors on e.g. binary content or resource references); (b) quarantine unreadable schemas at load time rather than broadening the allowed set.

### 3. Compaction handoff safety + turn timeout — `src/engine/context/compactor.py` + `src/engine/runner.py`
**Value: High / Effort: Medium**
`src/engine/context/compactor.py` runs compaction but may not guard against orphaned turns when a compaction stall races with a new request. OpenClaw's fix: preserve compaction ownership per session and surface a terminal outcome rather than hanging. Pair with a configurable turn timeout in `src/engine/runner.py` (default 180s, env-override).

### 4. Per-workspace model routing — `src/engine/llm/router.py`
**Value: Medium / Effort: Medium**
`src/engine/llm/router.py` currently routes by global config. OpenClaw shows a clean pattern: resolve model at dispatch time from a priority chain — per-request override → per-agent/workspace policy → global default — using provider-qualified IDs (`anthropic/claude-sonnet-5`, `openai/gpt-5.3`). Also: reject catalog responses over a size threshold before parsing.

### 5. Memory search + transcript embedding batching — `src/engine/memory/search.py` + `src/engine/memory/transcript_index.py`
**Value: Medium / Effort: Medium**
OpenClaw batches embeddings across files and caches the model catalog between sessions. `src/engine/memory/search.py` and `src/engine/memory/transcript_index.py` likely embed per-document; batching would reduce round-trips and respect provider batch-size limits (OpenClaw learned this the hard way: 2026.6.8 fixed 431 errors from oversized batches).

---

## Picks for Next Spike

1. **SQLite cron store** (`src/cron/store.py`) — highest durability payoff for lowest risk. Scope: add SQLite write path with atomic migration; keep JSON read path for rollback.
2. **Tool result normalization** (`src/engine/tools/registry.py`) — one defensive function at the tool-call return boundary. Small diff, eliminates a class of provider API errors.
3. **Turn timeout + compaction ownership** (`src/engine/runner.py`, `src/engine/context/compactor.py`) — good pairing: the timeout gives a recovery trigger, compaction safety prevents double-processing on resume.
