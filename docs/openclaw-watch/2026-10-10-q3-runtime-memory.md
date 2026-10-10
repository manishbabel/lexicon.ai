# OpenClaw Watch — 2026-10-10 (Q3 / Early Q4 Surge)

**Period covered:** 2026.5.27 (prior baseline) → 2026.9.9 stable / 2026.10.1-beta.2  
**Sources:** github.com/openclaw/openclaw/releases (fetched 2026-10-10), web aggregators

---

## What shipped

| Version | Date | Type | Headline |
|---------|------|------|----------|
| 2026.10.1-beta.2 | 2026-10-08 | pre-release | Hotfix: update/Doctor recovery, Discord/Telegram messaging, plugin skill availability during updates, Code Mode tool-schema fix |
| **2026.9.9** | 2026-10-08 | **stable** | 185 commits, 112 PRs, 92 contributors; Android APK skipped; Telegram checks waived |
| 2026.10.1-beta.1 | 2026-10-05 | pre-release | Code Mode `store`/`load`, transcript import, off-machine backups (R2/NAS), automation conditions without model run, MCP allowlists, installed-skill search, memory pre-compaction flush, GitHub Enterprise for cloud workers; **breaking change** for plugins importing retired compat facades |
| 2026.9.8 | 2026-10-03 | stable | 58 commits / 43 PRs; stabilisation |
| **2026.8.35** | 2026-10-02 | extended-stable | GPT-6.1 Sol support, safer update/recovery, more reliable agent completion, secret-handling hardening, **cron allowlists**, channel fixes (Gmail, Matrix, Telegram, MCP) |
| 2026.9.7 | ~Sep | stable | Snappier under load, smoother long sessions, update recovery, OpenAI Agents API, Sign in with ChatGPT (Beta) |
| 2026.9.5 | ~Sep | stable | Plugin install without restart, **teams of specialist agents**, GPT Live in calls |
| 2026.9.4 | ~Sep | stable | Skills easier to find, turn conversations into reusable skills |

---

## What's notable (patterns worth porting)

### 1. Session-scoped key-value store (2026.10.1-beta.1)
Code Mode gains explicit `store key value` / `load key` primitives for ephemeral, session-scoped state. Agents can stash computed artefacts (entity IDs, extracted counts, resolved ambiguities) and retrieve them in later turns without re-running LLM calls. The store is distinct from conversation memory — it is intentional, typed, and short-lived.

### 2. Memory pre-compaction flush (2026.10.1-beta.1)
Before the context compactor runs, memory plugins are required to flush any pending writes. This prevents a compaction cycle from silently dropping working-memory entries that have been updated but not persisted. The hook is explicit: plugins register a `before_compact` callback.

### 3. Automation conditions without model invocation (2026.10.1-beta.1)
Scheduled or event-triggered automations can gate on a lightweight condition check (field comparison, regex match against a stored value, time window) without paying for an LLM round-trip. Expensive model invocations only run when the condition passes.

### 4. Cron allowlists + secret-handling hardening (2026.8.35)
Cron jobs must declare an explicit set of allowed tool calls. Jobs that try to invoke tools outside their allowlist are rejected at dispatch, not at execution. Secret access is also tightened: cron context no longer inherits the full agent secret scope by default.

### 5. Agent completion reliability + update recovery (2026.8.35 / 2026.9.8 / 2026.9.9)
Three back-to-back releases (2026.8.35 → 2026.9.8 → 2026.9.9) all cite "more reliable agent completion" and "safer update/recovery." The common thread: agents that stall mid-run (network drop, provider timeout, OOM) are now checkpointed at task boundaries rather than at arbitrary yield points, and the runner replays from the last clean checkpoint on restart.

---

## What we can use in Lexicon

Ranked by value-to-effort ratio (high value first), each mapped to a verified file.

| # | Pattern | Value | Effort | Lexicon target |
|---|---------|-------|--------|----------------|
| 1 | **Session-scoped KV store** | High | Low | `src/engine/memory/working.py` — add `put(key, value)` / `get(key)` / `clear()` to `WorkingMemory`; scope to session lifetime |
| 2 | **Automation conditions without model run** | High | Medium | `src/cron/scheduler.py` — add a `condition` field to job definitions evaluated before dispatching to the engine |
| 3 | **Memory pre-compaction flush** | Medium | Low | `src/engine/context/compactor.py` — fire a `before_compact` hook that drains pending `WorkingMemory` / episodic writes before truncating context |
| 4 | **Cron allowlists** | High (security) | Medium | `src/cron/store.py` + `src/cron/scheduler.py` — persist an `allowed_tools` list per job; enforce in scheduler dispatch |
| 5 | **Agent checkpoint-based recovery** | Medium | High | `src/engine/runner.py` + `src/engine/runtime.py` — checkpoint task state at clean yield points; replay from last checkpoint on restart |

---

## Spike picks

**Spike 1 — `WorkingMemory` named store** (`src/engine/memory/working.py`)  
Lowest lift, highest day-to-day payoff. Agents writing entity IDs or extracted values back into working memory via `put/get` instead of re-prompting saves latency and cost. Can ship as a thin wrapper over the existing dict.

**Spike 2 — Cron condition gates** (`src/cron/scheduler.py`)  
The cron scheduler already runs scheduled jobs; adding a `condition` predicate evaluated before engine dispatch is additive. Start with simple comparisons (last-run status, stored value match) and expand later. Prevents burning LLM tokens on no-op runs.
