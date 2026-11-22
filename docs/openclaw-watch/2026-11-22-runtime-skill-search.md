# OpenClaw Watch — 2026-11-22

**Digest slug:** runtime-skill-search  
**Last seen before this run:** stable `2026.5.27` / beta `2026.5.28-beta.2` (checked 2026-09-23)

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.9.37 | Sep 2026 | Stable | Gateway stability and channel reliability fixes |
| 2026.10.33 | 18 Nov 2026 | Extended-stable (LTS) | Memory runtime overhaul, compaction, automations, security hardening |
| 2026.11.1–2026.11.6 | 1–19 Nov 2026 | Stable | Settings safety, update recovery, auth fixes |
| 2026.11.10-beta.1 | 19 Nov 2026 | Beta | Agent templates, on-demand tool index, durable execution |

**Newest stable:** `2026.11.6` (19 Nov 2026, 406 commits, 386 PRs, 157 contributors)  
**Newest beta:** `2026.11.10-beta.1` (19 Nov 2026)

Primary release notes sourced from the GitHub releases page and `v2026.10.33` extended-stable notes. `docs.openclaw.ai` was unreachable from this environment.

---

## What's notable

### 1. On-demand skill search (beta `2026.11.10-beta.1`, extended-stable `2026.10.33`)
Installed skills are now indexed and fetched on-demand by relevance rather than bulk-loaded into every prompt. An opt-in, usage-ranked tool index covers both native skills and MCP tools. This directly attacks the context-bloat problem for agents with many installed skills.

### 2. Provider-neutral memory runtime with checkpoint continuity (`2026.10.33`)
Memory uses host-resolved audiences and providers own their pre-compaction flushes. Compaction checkpoints now survive credential or model changes on the same provider endpoint, eliminating history replay on routine credential rotation. Provider-native compaction is used on supported OpenAI and Anthropic API-key routes.

### 3. Large-history OOM bounds (`2026.10.33`)
Transcript trimming, indexing, memory export, and Doctor repair are all now bounded to prevent out-of-memory failures. Large-history preparation was moved off the Gateway main thread in `2026.11.10-beta.1`, reducing cold-session compaction CPU and latency.

### 4. Event-driven automations (`2026.10.33`)
Cron automations can now react to polled conditions and MCP events, not just clock time. Session-targeted cron replies are retained across restarts. Active turns keep running across automatic session rollover.

### 5. Durable subagent queues across restarts (`2026.11.10-beta.1`)
Subagent results survive Gateway restarts. Background commands on macOS keep running across restarts. Gateway state at startup migrates via copy-and-swap rather than in-place edits, reducing corruption risk during interrupted updates.

---

## What we can use in Lexicon

Ranked by value-to-effort ratio. Each suggestion maps to a real file in this repo.

### 1. On-demand skill search — `src/engine/skills.py`
**Value:** High | **Effort:** Medium

Lexicon's `src/engine/skills.py` currently loads all workspace skills for every session. OpenClaw's pattern: build a usage-ranked index at startup and retrieve only the top-k skills by embedding similarity to the current turn context. This keeps prompts lean as the workspace skill count grows.

Spike entry point: `src/engine/skills.py` — add a `SkillIndex` class that scores skills against the active context before injection.

### 2. Bounded transcript indexing to prevent OOM — `src/engine/memory/transcript_index.py`
**Value:** High | **Effort:** Low

`src/engine/memory/transcript_index.py` performs full-history scans. OpenClaw's fix: bound all indexing and export operations with a window size cap. Add a `max_turns` parameter and enforce it before any scan; log a truncation warning so operators know the cap was hit.

Companion: `src/engine/memory/manager.py` — apply the same cap to memory export paths.

### 3. Compaction checkpoint continuity — `src/engine/context/compactor.py`
**Value:** High | **Effort:** Medium

`src/engine/context/compactor.py` and `src/engine/memory/working.py` likely replay history when the LLM provider or API key changes. OpenClaw's pattern: store a checkpoint keyed to `(provider_type, endpoint)` rather than the full credential, so rotations don't invalidate the checkpoint. Prevents expensive history replays during routine key rotation.

### 4. Event-driven cron triggers — `src/cron/scheduler.py`
**Value:** Medium | **Effort:** Medium

`src/cron/scheduler.py` and `src/cron/store.py` currently schedule by time only. OpenClaw's extension: add a `trigger` field to cron entries that can be a polled condition expression or an MCP event name. The scheduler polls the condition before firing rather than firing on every tick. Useful for Lexicon's heartbeat-driven agents.

Companion: `src/cron/defaults.py` — add default condition-trigger examples.

### 5. Queue durability across restarts — `src/engine/queue.py`
**Value:** Medium | **Effort:** Medium

`src/engine/queue.py` holds in-flight tool and subagent results in memory. OpenClaw's pattern: checkpoint queued results to the store on each state transition and recover them on startup via `src/engine/runner.py`. This prevents silent result loss when the engine restarts mid-run.

---

## My picks for what to spike next

**Highest priority:** On-demand skill search in `src/engine/skills.py`. Lexicon workspaces already have multiple skills each (e.g. `workspaces/software-engineer/skills/` has 8), and the agent count will grow. Front-loading all skills into every prompt is a compounding cost. A simple embedding-similarity filter before injection is achievable in a focused spike and has an immediate impact on token spend and latency.

**Second priority:** Bounded transcript indexing in `src/engine/memory/transcript_index.py`. This is the lowest-effort change with meaningful reliability upside — adding `max_turns` guards is a one-session spike that prevents production OOM on long-running agents.
