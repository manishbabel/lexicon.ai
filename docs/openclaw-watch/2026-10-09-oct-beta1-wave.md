# OpenClaw Watch — 2026-10-09

**Stable:** 2026.9.9 (Oct 8) | **Beta:** 2026.10.1-beta.2 (Oct 8) | **Extended-stable:** 2026.8.35 (Oct 2)

---

## What shipped

This digest covers all releases since the baseline (2026.5.27 / 2026.5.28-beta.2, last checked 2026-09-23). OpenClaw shipped roughly four months of releases across three lines.

| Version | Date | Line | Headline |
|---|---|---|---|
| 2026.10.1-beta.2 | Oct 8 | Pre-release | Hotfix: 40 commits. Auth, rollback recovery, channel repairs. |
| 2026.9.9 | Oct 8 | Stable | 185 commits, 112 PRs, 92 contributors. No detailed notes in public excerpt. |
| 2026.10.1-beta.1 | Oct 5 | Pre-release | Major feature wave: scheduling, memory, skills, session state. |
| 2026.9.8 | Oct 3 | Stable | 58 commits, 43 PRs. No public details in excerpt. |
| 2026.8.35 | Oct 2 | Extended-stable | LTS-class: security, agent-reliability, channel fixes. |
| 2026.9.6 / 2026.9.7 | ~Sep 6–7 | Stable | Listed in changelog but details unavailable in sources checked. |

**Source:** https://github.com/openclaw/openclaw/releases

---

## What's notable

### 1. Condition-gate scheduling (2026.10.1-beta.1)
Automations can now run a condition script **before** deciding whether to fire a full model run. Scripts have access to explicitly allowed MCP servers. The `cron.triggers.enabled` flag defaults to `true`, meaning all event triggers are live unless opted out.

Pattern: a scheduling step that evaluates a cheap predicate (file changed? queue non-empty? threshold crossed?) before spending a model call. The same pattern decouples trigger detection from model invocation.

### 2. Budget-aware skill loading (2026.10.1-beta.1)
Installed skills can be searched and read even when their instruction blocks don't fit the initial prompt budget. Skills are materialised lazily on demand rather than stuffed upfront into context.

Pattern: deferred/lazy skill materialisation with an out-of-band search index, so skill count doesn't inflate every prompt.

### 3. Memory plugin flush ownership (2026.10.1-beta.1)
Memory plugins can now own their pre-compaction flush — they flush their own state before the compactor fires, preventing data loss on rollbacks. Also: session-indexing locks are avoided on rollback-journal databases.

Pattern: a flush hook in the memory manager that each plugin implements, called in order before any compaction pass.

### 4. Session-scoped value store (2026.10.1-beta.1)
Code Mode gains `store` and `load` primitives for session-scoped key-value state, with enforced size limits. This is lightweight ephemeral state — it doesn't write to episodic memory.

Pattern: a thin key-value store on the session object for transient in-run state, avoiding expensive memory writes for values that only need to survive the current session.

### 5. Per-automation MCP allowlist + secret-store rotation safety (2026.10.1-beta.1, 2026.8.35)
Each scheduled automation carries an explicit list of MCP servers it may call. Separately, the extended-stable line keeps secret-store kinds stable through rotation so active agents don't lose their credentials mid-run.

Pattern: allowlist-scoped tool access at the automation level (not just at the agent level), and idempotent secret rotation.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified to exist in `src/`.

### 1. Condition-gate scheduling — HIGH value / LOW effort
**Map to:** `src/cron/scheduler.py` + `src/cron/defaults.py`

Add an optional `condition` expression or script to cron entries. The scheduler evaluates the condition cheaply (Python expression, or a small tool call against an allowed MCP server) before handing off to the engine. If the condition is falsy, the slot is skipped without a model call. `src/cron/store.py` already persists run state, so condition results can be cached between checks.

### 2. Budget-aware / lazy skill loading — HIGH value / MEDIUM effort
**Map to:** `src/engine/skills.py`

Lexicon currently loads all applicable skills into the initial prompt. Adding a searchable skill index (names + short descriptions only) lets the engine materialise full skill text on demand when an agent explicitly requests one, keeping base context lean. Pairs with the context management already in `src/engine/context/pruner.py`.

### 3. Session-scoped key-value store — MEDIUM value / LOW effort
**Map to:** `src/engine/runtime.py` + `src/gateway/session.py`

A small dict on the runtime/session object, size-capped (e.g. 64 KB total), cleared at session end. Gives agents a place to stash transient state (a running count, a dedup set, a flag) without writing to `src/engine/memory/episodic.py`. Implement as a `session.store` / `session.load` pair exposed to tools.

### 4. Memory plugin pre-compaction flush hook — MEDIUM value / MEDIUM effort
**Map to:** `src/engine/memory/manager.py` + `src/engine/context/compactor.py`

`src/engine/context/compactor.py` fires compaction; `src/engine/memory/manager.py` owns the plugin registry. Add a `pre_compact()` hook on memory plugins that `compactor.py` calls before it runs. Each plugin (e.g. `src/engine/memory/episodic.py`) implements `pre_compact()` to flush its write buffer. Prevents the data-loss-on-rollback class of bugs OpenClaw's 2026.10.1-beta.1 patched.

### 5. Per-cron MCP server allowlist — MEDIUM value / LOW effort
**Map to:** `src/cron/scheduler.py` + `src/cron/defaults.py`

Add an `allowed_mcp_servers` field to cron job definitions (default: none). The scheduler passes only those servers to the engine when spawning the run, rather than inheriting the full gateway tool list. Low effort if the engine already accepts a tool filter at invocation time.

---

## Picks for the next spike

1. **Condition-gate scheduling** (`src/cron/scheduler.py`) — fastest win. Prevents model calls on quiet queues; the pattern is self-contained and doesn't touch memory or the LLM layer.

2. **Budget-aware skill loading** (`src/engine/skills.py`) — addresses a real scaling constraint. As Lexicon's skill library grows, prompt bloat from upfront skill injection will become a bottleneck. A lazy index is the right fix before it hurts.
