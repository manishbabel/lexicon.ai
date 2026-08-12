# OpenClaw Watch — 2026-08-12: Resilience & Recovery

## What Shipped

| Version | Published | Type | Headline |
|---|---|---|---|
| **2026.6.34** | ~Aug 8, 2026 | Stable (extended-maintenance) | Sandboxed routes, provider fallbacks, channel recovery, SQLite checkpoints |
| 2026.7.1-1 | Aug 4, 2026 | Patch | Codex progress replies, Memory Core startup repair, legacy migration cleanup |
| 2026.7.1-2 | Aug 4, 2026 | Hotfix | npm plugin singleton-array metadata fix |
| **2026.7.2-beta.7** | Aug 2, 2026 | Beta | Quarantine stores, dead-letter recovery, conversation forking, structured approvals |

**Baseline we tracked from:** 2026.5.27 stable / 2026.5.28-beta.2.

The 2026.7.1 patch builds are operational repairs (Codex, npm, WSL) — no new patterns. The two worth studying are 2026.6.34 (now stable, ships in production installs) and 2026.7.2-beta.7 (preview of the next major).

---

## What's Notable

### 1. Provider fallback with session retention (2026.6.34)
When a provider call fails, OpenClaw retries via a configured fallback chain rather than terminating the session. Session writes are retained across the failure. This is distinct from simple retry — it routes to a different backend entirely while keeping the in-flight conversation intact.

### 2. Idempotent channel acknowledgements + pending work resumption (2026.6.34)
Channel acknowledgements are now idempotent: duplicate ACKs from a retried delivery are safe. More importantly, pending queued work resumes after an outage rather than being silently dropped. Discord gateway burst traffic is now bounded via a token bucket.

### 3. Quarantine stores for primary-DB damage (2026.7.2-beta.7)
A secondary "quarantine store" survives even when the primary database is corrupted. Schema-upgrade data-loss is rejected rather than silently migrated. Crash-recoverable SQLite snapshots are written before destructive operations.

### 4. Dead-letter recovery across channels (2026.7.2-beta.7)
Accepted messages (those that passed ingress validation) are persisted in a dead-letter store before processing. On restart, the ingress drain replays them. Covers Telegram, Signal, Slack, QQBot.

### 5. Conversation forking/branching (2026.7.2-beta.7)
Users can rewind a conversation to any prior message and fork a new branch from that point. Forked sessions preserve branch-safe queued sends — messages queued in the parent branch don't bleed into the fork.

---

## What We Can Use in Lexicon

Ranked by **value / effort**. Each file path verified to exist in `src/`.

### 1. Provider fallback chain in `PersonaLLMRouter` — HIGH value / LOW effort
**File:** `src/engine/llm/router.py:75` (`_get_provider`)

Today `_get_provider` raises immediately on an unsupported provider name and propagates uncaught provider errors up through the agent run. OpenClaw's pattern: hold an ordered fallback list per persona (e.g. `["anthropic", "litellm"]`), catch provider-level exceptions in `resolve()`, and re-resolve with the next entry before surfacing the error to the session. The session stays alive; the caller sees the response from whichever backend succeeded.

Spike: add `_fallback_chain: list[str]` to `PersonaLLMRouter.__init__`, wrap the `_get_provider` call in `resolve()` with a `for provider_name in [primary] + fallbacks` loop.

### 2. Atomic writes in `CronJobStore` — MEDIUM value / LOW effort
**File:** `src/cron/store.py:122` (`save`)

`save()` does a direct `Path.write_text()`. A crash mid-write produces a truncated `jobs.json` that silently returns `[]` on the next load (see `load()` line 106-108). OpenClaw's pattern: write to `jobs.json.tmp`, then `os.replace()` (atomic on POSIX). One-line change; eliminates the corruption window.

Spike: replace `self._path.write_text(...)` with write-to-tmp + `os.replace(tmp, self._path)`.

### 3. Queued-work persistence for `CommandQueue` — HIGH value / HIGH effort
**File:** `src/engine/queue.py:132` (`_session_queues`)

`_session_queues` is a plain `defaultdict(list)`. If the process restarts while messages are queued or a run is in-flight, that work is gone. OpenClaw's dead-letter pattern: before calling `_run_handler`, serialize the `AgentRun` (including its `input_messages`) to a WAL file; remove the entry on clean completion; replay surviving entries on startup. Touches `CommandQueue`, `AgentRun`, and wherever the queue is initialized in the gateway.

### 4. Idempotent session ACKs in `SessionManager` — MEDIUM value / MEDIUM effort
**File:** `src/gateway/session.py:89` (`end_session`)

`end_session` is not idempotent — calling it twice on the same ID logs a warning and returns `None` but does not re-confirm the clean state. Separately, `resume_session`/`pause_session` silently no-op on unknown IDs. OpenClaw's pattern: track a `last_ack_id` per session so duplicate control messages from a retrying client don't cause double-teardown or double-resume. Low-risk, pairs with the queue persistence work.

### 5. Conversation forking anchored to `TranscriptIndex` — MEDIUM value / HIGH effort
**File:** `src/engine/memory/transcript_index.py`

OpenClaw forks from a specific message in the transcript. Lexicon's `transcript_index` already indexes session transcripts; a fork would mean snapshotting the index state at a given message ID, cloning the `SessionState` with a new `id`, and linking the forked session's memory context to the snapshot. Useful for "replay from before this wrong turn" or experimentation without polluting episodic memory. Effort is high — requires changes across `SessionManager`, `MemoryManager`, and the gateway protocol — but the index file is a natural anchor point.

---

## Picks to Spike Next

**Spike 1 (do now):** Provider fallback chain in `src/engine/llm/router.py`. An afternoon's work. The risk of a single provider flapping and killing an active session is real; this eliminates it with minimal blast radius.

**Spike 2 (do now, same PR):** Atomic `CronJobStore` writes in `src/cron/store.py`. A three-line change. The current code is silent-corruption-on-crash; the fix is safer by default.

**Spike 3 (next sprint):** Queue persistence / dead-letter replay in `src/engine/queue.py`. Larger but the right move before scaling the number of concurrent sessions. Skip until Spike 1+2 are merged and any regressions are clear.
