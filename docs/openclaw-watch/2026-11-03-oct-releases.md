# OpenClaw Watch — 2026-11-03 Digest

**Coverage:** 2026.6.1 → 2026.10.10 (stable), 2026.10.10-beta.5 (beta)
**Prior baseline:** 2026.5.27 stable / 2026.5.28-beta.2 beta (last checked 2026-09-23)

---

## What Shipped

| Version | Approx Date | Headline |
|---|---|---|
| 2026.6.1 | Jun 2026 | Cron → SQLite, Skill Workshop, async static asset serving |
| 2026.7.1 | Jul 2026 | Condition-watching cron, GPT-5.6/Claude Sonnet 5 models, scoped external-tool access |
| 2026.8.1 | Aug 2026 | Active Memory dreaming, Swarm subagents, on-demand provider install, A2A channels |
| 2026.9.1 | Sep 2026 | Dynamic LLM catalog refresh, per-agent `cwd`, `skipMissedJobs`, `blockedHostnames` SSRF |
| 2026.10.10 | Nov 3 2026 | Incremental transcript indexing, event-triggered automations, LLM priority scheduling, MCP Relay |
| 2026.10.10-beta.5 | Oct 30 2026 | Node 26 stdin fix, gateway streaming stall fix, cron restart recovery |

Full release notes: https://github.com/openclaw/openclaw/releases

---

## What's Notable (5 Patterns)

### 1. Incremental Transcript Indexing (2026.10.10)
Transcripts are indexed after a quiet period (not immediately on every chunk). Unchanged indexed chunks are reused; only modified content is re-embedded. Searches use the last published index rather than waiting for in-flight indexing. A managed one-concurrent-file limit prevents memory spikes during rebuilds.

**Why it matters:** eliminates redundant re-embedding of stable content and decouples the hot path from index writes.

### 2. Condition-Watching Automations (2026.7.1)
Cron jobs can watch a condition: the payload fires only when the condition's state changes, not on every timer tick. Reapplying a job declaration updates it in place, preserving history and avoiding duplicate registrations.

**Why it matters:** reduces wasted model invocations for polling jobs that check the same state repeatedly.

### 3. LLM Priority Scheduling (2026.10.10)
A per-model option designates whether a turn is `interactive` or `background`. Interactive turns and manual compaction get priority over background work sharing the same model endpoint.

**Why it matters:** prevents background jobs (cron digests, heartbeat checks) from starving live conversation turns when a single provider is shared.

### 4. Memory Dreaming / Background Consolidation (2026.8.1)
After a quiet period, a background pass runs a model over recent episodic entries to extract durable lessons and promote them to long-term memory (with a provenance tag). Users can run `openclaw memory forget` to remove derived memory without deleting source transcripts.

**Why it matters:** surfaces cross-meeting patterns that pure retrieval misses; keeps working memory lean.

### 5. `skipMissedJobs` + Malformed Row Quarantine (2026.9.1)
`cron.skipMissedJobs: true` prevents catchup fires for recurring jobs missed during downtime. Malformed persisted job rows are quarantined (not deleted) rather than blocking the scheduler from starting.

**Why it matters:** prevents thundering-herd on restart and makes the scheduler resilient to schema drift.

---

## What We Can Use in Lexicon

Ranked by value / effort (highest first). Every file path is verified to exist in `src/`.

### 1. Incremental transcript indexing — `src/engine/memory/transcript_index.py`
**Value: High / Effort: Low-Medium**

`TranscriptIndexer.index_meeting` re-chunks the full meeting transcript every time. OpenClaw's pattern: hash each chunk, store hashes alongside the vault file, skip re-embedding chunks whose hash is unchanged. Add a `.hashes` sidecar file next to each `vault/transcripts/<meeting_id>.md`. Only changed or new chunks call the embed API. Also: defer `index_meeting` calls until the meeting is quiet (no transcript activity for N seconds) rather than indexing mid-stream.

### 2. Condition-watching cron jobs — `src/cron/scheduler.py` + `src/cron/store.py`
**Value: High / Effort: Low**

`CronJob` in `src/cron/store.py` has no notion of a watched condition. Add an optional `condition_hash: str | None` field. In `CronScheduler._execute_job`, before dispatching, compute a hash of the condition's current value (e.g., a file mtime, a count query, a lightweight probe). If the hash equals the stored value, skip the dispatch and update only the `last_run` timestamp. This avoids model invocations for jobs whose trigger state has not changed.

### 3. LLM priority queue — `src/engine/llm/router.py` + `src/engine/queue.py`
**Value: Medium-High / Effort: Medium**

`PersonaLLMRouter.resolve` returns a `ResolvedLLM` with no priority information. Add a `priority: Literal["interactive", "background"]` field to `ResolvedLLM` (defaulting to `"interactive"`). In `src/engine/queue.py`, where commands are enqueued, use a two-slot priority queue: interactive commands jump ahead of background ones. Cron-originated commands are `background`; gateway-originated commands are `interactive`.

### 4. Background memory consolidation — `src/engine/memory/episodic.py` + `src/cron/defaults.py`
**Value: Medium / Effort: Medium**

`EpisodicMemory` stores per-meeting JSONL but never aggregates across meetings. OpenClaw's dreaming pattern: add a nightly cron job in `src/cron/defaults.py` that reads recent episodic entries across all agents, calls the LLM for a short "what lessons or facts recurred this week?" prompt, and writes extracted items into `src/engine/memory/working.py` with a `source: "dream"` tag. Include a `forget` path: delete dream-derived entries while leaving episodic source files intact.

### 5. `skipMissedJobs` in cron store — `src/cron/store.py` + `src/cron/scheduler.py`
**Value: Medium / Effort: Low**

`CronScheduler.start` currently loads all jobs and registers them. Add `skip_missed_jobs: bool = True` to `CronJob` and pass `misfire_grace_time=0` to APScheduler for those jobs. Also wrap `CronJobStore._load` so that rows that fail validation are moved to a `quarantined` list (logged but not registered), rather than raising and aborting scheduler startup.

---

## My Picks for What to Spike Next

1. **Incremental transcript indexing** (`src/engine/memory/transcript_index.py`) — clear latency and cost win with contained blast radius; no schema changes needed, just a `.hashes` sidecar.
2. **Condition-watching cron** (`src/cron/store.py`, `src/cron/scheduler.py`) — one field addition and a pre-dispatch check; immediate reduction in wasteful model invocations for polling jobs.
