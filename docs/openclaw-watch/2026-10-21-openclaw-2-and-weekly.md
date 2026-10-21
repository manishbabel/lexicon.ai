# OpenClaw Watch — 2026-10-21

**Digest period:** 2026-05-27 → 2026-10-21  
**Latest stable:** v2026.10.5 (2026-10-18)  
**Latest beta:** v2026.10.10-beta.3 (2026-10-21)  
**Previous state:** stable 2026.5.27 / beta 2026.5.28-beta.2 (last checked 2026-09-23)

---

## What Shipped

### v2026.8.1 — OpenClaw 2.0 (2026-08-30) ⭐ Major
The 2.0 release is a structural rework of the memory subsystem:
- **QMD backend retired** as the default memory store; replaced with a built-in SQLite-backed memory that owns search and recall.
- **Active Memory** on by default for personal installations. Group/channel conversations excluded from the default recall path by design.
- **Dreaming** introduced: background process that promotes durable facts from in-flight context into a persistent `MEMORY.md`-style store while the agent is idle.
- **Silent flush before compaction**: working memory is flushed to persistent store before context compaction runs, preventing silent data loss.
- **Gateway startup** cut from ~1.6 s to ~575 ms; sessions and transcripts migrated to SQLite.
- **Storage migration note:** downgrade from 2.0 to 1.x requires manual conversion; backup before upgrading.

### v2026.9.33 — Extended-Stable / LTS gateway release
- **Interrupted turn resumption:** automation turns, steered sessions, cloud worker claims, and partial worker replies resume or persist across gateway restarts.
- **Agent store ownership:** updates on the 2026.9 line keep state, plugin data, and service ownership intact across schema changes; stores are restored after schema-changing updates.
- **Local provider deadlines:** agent runs honor live thinking levels; local providers get response-header deadlines.
- **Security:** critical security updates (details not public); Doctor no longer deletes an OAuth profile on unreadable legacy auth stores.

### v2026.10.10-beta.1 (2026-10-15)
- **Experimental PostgreSQL engine** for the Workboard store — first step toward a swappable persistence backend.
- **DB operations on worker threads** — non-blocking database I/O architecture.
- **Cloud sessions + local Gateways** in desktop app; new model catalog entries (Gemini 4 Argon).
- Breaking: requires macOS 26.2 / iOS 26.2 / Safari 26.2+.

### v2026.10.10-beta.2 (2026-10-19)
- **Workspace safety for multi-file apply_patch:** validates all targets before any file is changed; rejects the whole operation on a mismatch.
- **Hook coverage in standalone sessions:** `before_tool_call` hooks now fire in `openclaw agent exec` (non-gateway) runs.
- **Gateway SQLite crash loop fix**; cron history memory fix.

### v2026.10.10-beta.3 (2026-10-21, day-of)
- **Agent stores restored after schema-changing updates** (promoted from beta.2 groundwork).
- **Concurrent agent DB init safety:** concurrent agent database initialization now safe.
- **Memory indexing on cold gateway starts:** memory index is rebuilt reliably on cold starts.

---

## What's Notable

1. **Dreaming (background memory promotion):** The first OpenClaw pattern that crosses the memory/compaction boundary — facts that would otherwise be discarded during context trimming are now durably promoted in the background. This is the most transferable architectural idea in the 2.0 release.

2. **Silent flush before compaction:** Simple invariant — write volatile memory out *before* shrinking context, not after. Prevents the race condition where compaction discards facts that were never persisted.

3. **Interrupted turn resumption (2026.9.33):** Agent runs are now checkpointed across gateway restarts. The pattern: persist enough run state to re-enter the execution loop from the last safe point rather than starting over.

4. **Swappable store backend (PostgreSQL in beta.1):** The store layer is being abstracted so the same codebase can back single-user (JSON/SQLite) and multi-user (PostgreSQL) deployments. This prefigures a plugin-style persistence architecture.

5. **Hook coverage parity between gateway and standalone runs (beta.2):** Hooks registered at gateway startup were previously silent in `agent exec` sessions. The fix is an explicit hook bootstrap in the standalone entry path.

---

## What We Can Use in Lexicon

Ranked by value/effort ratio; each mapped to a real file that exists under `src/`.

### 1. Silent flush before compaction — HIGH value / LOW effort
**Pattern:** Call `memory.flush()` (or equivalent) before `Compactor` runs, so nothing in working memory is silently discarded.  
**Lexicon files:**
- `src/engine/context/compactor.py` — add a pre-compaction hook/call to flush memory before summarization begins.
- `src/engine/memory/manager.py` — expose a `flush()` method that writes working-memory entries to short-term or episodic JSONL.
- `src/engine/memory/working.py` — source of the entries to flush.

**Why now:** Compactor already runs; the only missing step is a flush gate at the top of `Compactor.compact()`. One function call, no new dependencies.

### 2. Hook coverage in standalone / cron sessions — HIGH value / LOW effort
**Pattern:** Bootstrap built-in hooks in any execution path that calls `AgentRuntime`, not just gateway startup.  
**Lexicon files:**
- `src/engine/hooks/builtin.py` — `register_builtin_hooks()` is documented as called "during gateway startup."
- `src/engine/runner.py` — `AgentRunner` sets up the execution context but doesn't call `register_builtin_hooks()`.
- `src/cron/scheduler.py` — cron-triggered runs go through `AgentRunner` without gateway boot.

**Why now:** The hooks (e.g., QMD reindex after vault write) are silently absent for any cron- or CLI-triggered run. Low risk change: add the bootstrap call in `AgentRunner.__init__` or `AgentRunner.run()`.

### 3. Memory indexing on cold gateway start — MEDIUM value / LOW effort
**Pattern:** On Gateway startup, unconditionally rebuild or validate the memory/transcript index rather than assuming it is current.  
**Lexicon files:**
- `src/engine/memory/transcript_index.py` — the index that should be validated/rebuilt on cold start.
- `src/gateway/server.py` — startup entry point; add an index-integrity check here.

**Why now:** Prevents stale search results after an unclean shutdown. One `await index.ensure_ready()` call at startup.

### 4. Dreaming / background memory promotion — HIGH value / MEDIUM effort
**Pattern:** A lightweight background coroutine that periodically scans `WorkingMemory` for fact-like entries and promotes them to `EpisodicMemory` while the agent is idle, without blocking the run loop.  
**Lexicon files:**
- `src/engine/memory/working.py` — source of candidate facts.
- `src/engine/memory/episodic.py` — destination store.
- `src/engine/memory/manager.py` — orchestrate the promotion loop.
- `src/engine/runtime.py` — spawn the background task from the runtime lifecycle.

**Why medium effort:** Requires a promotion heuristic (what counts as "durable"), a de-duplication pass, and a way to cancel the task cleanly on shutdown. Worth a dedicated spike.

### 5. Interrupted turn resumption — MEDIUM value / HIGH effort
**Pattern:** Checkpoint run state (current message list, run ID, agent identity) to durable storage before the run starts; on restart, detect incomplete runs and resume from the checkpoint.  
**Lexicon files:**
- `src/engine/runner.py` — `AgentRunner.run()` is the entry point; checkpoint here.
- `src/engine/queue.py` — `AgentRun` and `QueuedMessage` are the units of work; they need durable IDs and status fields.
- `src/cron/store.py` — an analogous pattern already exists for cron jobs (status + last_run persisted to JSON); the same idiom can be ported to the run queue.

**Why high effort:** Requires a durable run-state store, a recovery scan at startup, and careful handling of non-idempotent tool calls.

---

## Picks for Next Spike

1. **Silent flush before compaction** (`src/engine/context/compactor.py` + `src/engine/memory/manager.py`) — an afternoon's work that closes a real data-loss path and directly mirrors OpenClaw 2.0's most actionable change.

2. **Hook coverage in standalone/cron sessions** (`src/engine/hooks/builtin.py` + `src/engine/runner.py`) — hooks are already written; they just need to be bootstrapped outside the gateway startup path. Guards cron-run integrity today.

---

*Sources: GitHub releases page (github.com/openclaw/openclaw/releases), web search results aggregating OpenClaw 2.0 coverage (InfoQ, Cellcog, flowtivity.ai, intelligentliving.co). docs.openclaw.ai and releasebot.io were unreachable from this environment.*
