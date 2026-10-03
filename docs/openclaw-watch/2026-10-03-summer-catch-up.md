# OpenClaw Watch: 2026-10-03 Summer Catch-up Digest

> Covers stable 2026.5.27 → **2026.9.8** and extended-stable through **2026.8.35**.
> Last checked: 2026-09-23. Today: 2026-10-03.

---

## What Shipped

| Track | Version | Date | Headline |
|-------|---------|------|----------|
| Stable | **2026.9.8** | 2026-10-03 | 58-commit point release; npm-signed |
| Stable | 2026.9.7 | 2026-09-30 | Performance under load, update recovery, OpenAI Agents API |
| Stable | 2026.9.6 | 2026-09-23 | Background tasks from command palette; personal themes |
| Stable | 2026.9.5 | ~2026-09-15 | Hot-installing plugins; specialist agent teams; GPT Live in calls |
| Stable | 2026.9.2 | ~2026-09-10 | Reliability/recovery pass; GPT-6 Astra + Meta Muse Spark 1.3 |
| Stable | **2026.8.1** | ~2026-08-01 | OpenClaw 2.0 — full runtime/memory/scheduling rebuild |
| Stable | 2026.7.1 | ~2026-07-01 | Control UI overhaul; channel reliability; change-driven scheduling |
| Extended-stable | 2026.8.35 | 2026-10-02 | GPT-6.1 Sol support; child-capacity deadlock fix; secret rotation |
| Extended-stable | 2026.8.34 | 2026-10-02 | 113 audit-fix units; authentication and session hardening |
| Extended-stable | 2026.8.33 | 2026-09-29 | GPT-5.6 family; Prometheus metrics; Discord ownership security |

---

## What's Notable (Patterns Worth Tracking)

### 1. Change-driven scheduling (v2026.7.1)
Scheduled work can wake "only when something changes" rather than firing on a fixed interval regardless of state. This is a first-class trigger type alongside cron/every/at — the job registers interest in a resource or event and runs only when a delta is detected. Eliminates wasted no-op runs.

### 2. Persisted delegation permissions (v2026.8.1)
Replaced per-request approval gates with **granted permissions**: an automation can be given permission for an exact operation, the grant is stored, and a fresh approval is required only when the job or the target operation changes. Revocable at any time. This shifts orchestration from "ask every time" to "trust + audit".

### 3. Private credential bypass (v2026.8.1)
Credentials are requested through a masked prompt path that **never enters model context**. A proxy limits substitution to approved destination hosts. Subprocesses spawned from a job cannot revive closed proxy connections after the run ends. The whole secret lives outside the conversation.

### 4. Child capacity release on delegated tasks (v2026.8.35)
Sub-agents that complete must explicitly release their capacity reservation. "Release suspended child capacity" prevents resource deadlocks in chains where a delegator waits on a delegatee that already exited. Also: failed requests no longer consume capacity from question-routing slots.

### 5. Transcript branching / rewind-fork (v2026.8.1)
Sessions support rewinding to any persisted user message and forking a new branch from that point. Branches are retained independently; active memory search is bounded per-agent. This enables exploratory and eval-style workflows without linear transcript accumulation.

---

## What We Can Use in Lexicon

Ranked by value/effort. Each entry maps to a file that exists in `src/`.

### 🟥 High value / Low effort
**Child capacity release — `src/engine/orchestrator.py`**
The `Orchestrator` creates isolated sub-agent runtimes (`ONESHOT`) but has no explicit capacity accounting. If a sub-agent run raises before returning, the delegator stalls with no release path. Add a try/finally that always calls a `_release_capacity(run_id)` hook, and track active sub-agent count so a saturated orchestrator can back-pressure callers rather than deadlocking.

### 🟥 High value / Medium effort
**Change-driven scheduling — `src/cron/scheduler.py`**
The scheduler supports `cron`, `every`, and `at` schedule types. Add an `event` type: a job registers a watcher function (e.g., `vault_changed`, `new_meeting_transcript`), and the scheduler only fires when the watcher signals a delta. APScheduler's `listen_to` hook or a simple polling diff with state hash can implement this without replacing the existing trigger logic.

### 🟥 High value / Medium effort
**Private credential bypass — `src/engine/llm/provider.py` + `src/shared/config.py`**
Currently LLM providers receive credentials through config dicts that flow through the same code path as the rest of the system prompt context. Add a `SecretRef` type in `src/shared/config.py` that resolves at call time and is never serialized to logs or messages. The router in `src/engine/llm/router.py` can unwrap `SecretRef` just before the API call; the raw value never enters agent messages or `src/shared/logger.py` output.

### 🟨 Medium value / Medium effort
**Persisted approval permissions — `src/cron/scheduler.py`**
Cron jobs have `target.agent` and `target.skill` but no approval layer. Add an optional `permissions` field to `CronJob` (in `src/cron/store.py`) — a dict of `{operation: granted_at}` entries. The scheduler checks the grant before executing and demands re-approval if the job's command or target changes post-grant. Low surface area: one field on the model, one check in `_execute_job`.

### 🟩 Medium value / High effort
**Transcript branching — `src/engine/memory/transcript_index.py`**
The transcript index already persists messages. Branching requires adding a `parent_message_id` pointer and a `branch_id` to each entry, then teaching `MemoryManager` to scope recall to a specific branch. High effort because it ripples into `src/engine/memory/short_term.py`, `src/engine/context/compactor.py`, and the gateway session model.

---

## Spike Picks

**Spike 1 (this week):** Child capacity release in `src/engine/orchestrator.py`. One try/finally block and a counter. Zero risk to existing behavior, prevents a latent deadlock class.

**Spike 2 (next sprint):** Change-driven scheduling in `src/cron/scheduler.py`. The `event` trigger type. Start with a `vault_changed` watcher for the blog-monitor and paper-fetch jobs — they currently fire on interval whether or not new content exists.

---

*Sources: github.com/openclaw/openclaw/releases (primary), web search (secondary). docs.openclaw.ai and releasebot.io blocked by network egress policy this run.*
