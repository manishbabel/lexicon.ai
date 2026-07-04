# OpenClaw Watch — 2026-07-04

## What Shipped

| Release | Date | Type |
|---|---|---|
| **2026.6.11** | 2026-06-30 | Stable |
| 2026.6.11-beta.2 | 2026-06-28 | Beta |
| 2026.7.1-beta.1 | 2026-07-02 | Beta |

Baseline was **2026.5.27** stable / **2026.5.28-beta.2** beta.

### 2026.6.11 (Stable) — headline
Reliability sweep: channel delivery, session continuity after reconnects, memory search timeouts, context compaction safety, and package trust hardening.

### 2026.7.1-beta.1 — headline
New primitives: event-driven `on-exit` cron scheduling, per-conversation capability profiles, external harness attachment (`openclaw attach`), run-cache growth cap, and mid-stream failure recovery.

---

## What's Notable

### 1. Memory search background-task timeout (2026.6.11)
QMD/vector searches now enforce a hard timeout and cancel background work on expiry, preventing zombie workers that accumulated silently across long sessions. The fix distinguishes "timed out" from "no results" so callers can retry intelligently rather than treating silence as an empty result set.

### 2. Context compactor turn-loss prevention (2026.6.11)
When a session is compacted under memory pressure, the compactor now preserves boundary turns (the most recent user+assistant pair) and validates the summary round-trip before discarding originals. Previously a compaction race could swallow the last human turn, producing confused continuations.

### 3. Event-driven `on-exit` cron trigger (2026.7.1-beta.1)
A new schedule kind fires a cron job when a watched shell command exits — rather than on a wall-clock interval. This lets agents react to external completions (a build finishing, a file arriving) without polling. The trigger integrates into the existing APScheduler job model; session-targeted runs detach cleanly to avoid blocking the watcher loop.

### 4. Per-conversation capability profiles (2026.7.1-beta.1)
The runtime now assembles a restricted tool+access boundary per conversation before the first agent turn, without modifying the global default profile. Each conversation declares which tools it needs; anything else is excluded from the system prompt and tool list. This limits blast radius if a conversation is hijacked via prompt injection.

### 5. Run-cache growth cap (2026.7.1-beta.1)
Gateway run-cache (completed run metadata kept for status polling) now evicts entries beyond a configurable LRU ceiling, preventing unbounded heap growth in long-running gateway processes. Previously a gateway left running for days could accumulate tens of thousands of stale entries.

---

## What We Can Use in Lexicon

Ranked by **value / effort**. Every path verified in the working tree.

### 1. Memory search timeout enforcement — HIGH value / LOW effort
**File:** `src/engine/memory/search.py`
**Also:** `src/search/qmd_client.py`

`MemorySearcher` runs background MMR scoring but has no hard deadline. If QMD stalls (network hiccup, slow vault), the search silently blocks the agent turn. Port the cancellation pattern: wrap the search coroutine in `asyncio.wait_for(search_coro, timeout=cfg.memory_search_timeout_s)`, catch `asyncio.TimeoutError`, log it separately from empty-result, and surface it to the caller so it can fall back to short-term memory only.

---

### 2. Context compactor boundary-turn guard — HIGH value / LOW effort
**File:** `src/engine/context/compactor.py`

Current compactor summarizes "chunks of old conversation" but doesn't explicitly protect the boundary turn. Add a `_protect_boundary(messages)` step that always excludes the last user+assistant pair from the compaction batch, and validate the summary is non-empty before replacing originals. Prevents the most disorienting class of context loss.

---

### 3. Run-cache LRU eviction — MEDIUM value / LOW effort
**File:** `src/engine/queue.py`

`queue.py` holds run state per session lane. Long-running gateway processes accumulate finished lane metadata with no eviction. Add an LRU cap (e.g. 512 completed entries) using `collections.OrderedDict`. Wire eviction into the lane completion callback so it runs inline without a background task.

---

### 4. Per-conversation capability profiles — HIGH value / MEDIUM effort
**Files:** `src/engine/skills.py`, `src/engine/tools/registry.py`

Today every session sees the full tool registry and full skill list. Port the profile pattern: let each conversation carry a `capability_profile` (tool name allowlist + skill tag allowlist), defaulting to `"*"` for backward compat. `ToolRegistry` filters its exported schema list through the profile before injecting into the system prompt. `SkillRegistry` in `skills.py` does the same for skill descriptions. This directly limits what a prompt-injected instruction can invoke.

---

### 5. Event-driven `on-exit` cron trigger — MEDIUM value / MEDIUM effort
**File:** `src/cron/scheduler.py`

`CronScheduler` supports APScheduler triggers (interval, cron, date). Add a new trigger kind `on_exit` that wraps `asyncio.create_subprocess_exec`, awaits the process, then enqueues the job command when exit code matches a configured pattern. Wire it into `_execute_job()` alongside the existing trigger dispatch. Useful for Lexicon's audio pipeline (trigger a summary job when a recording ends) and vault sync jobs.

---

## My Picks to Spike Next

1. **Memory search timeout** (`src/engine/memory/search.py`) — one `asyncio.wait_for` wrapper, immediate reliability win for slow vault setups. Ship first.
2. **Compactor boundary-turn guard** (`src/engine/context/compactor.py`) — low-risk two-step guard that eliminates the worst class of context compaction bug.
3. **Per-conversation capability profiles** (`src/engine/skills.py` + `src/engine/tools/registry.py`) — highest security leverage; worth a focused spike once the above two are in.
