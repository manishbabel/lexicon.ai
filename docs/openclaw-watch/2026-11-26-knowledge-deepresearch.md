# OpenClaw Watch — 2026-11-26: Knowledge Memory + Deep Research

## What shipped

| Version | Type | Released | Headline |
|---|---|---|---|
| 2026.11.10 | Stable | 2026-11-25 | Knowledge memory provider, Deep Research, browser handoff |
| 2026.10.34 | Extended-stable | 2026-11-26 | System-prompt caching on OpenAI routes, update recovery |
| 2026.11.10-beta.3 | Pre-release | 2026-11-24 | Subagent answer persistence, memory compaction, SecretRef credentials |

Previous baseline: stable 2026.5.27 / beta 2026.5.28-beta.2 (last checked 2026-09-23)

---

## What's notable

### 1. Knowledge — pluggable, hot-reloadable memory provider (2026.11.10)
OpenClaw introduced a new `memory` plugin slot (`plugins.slots.memory`) wired into a local Markdown vault. Key design decisions worth studying:
- **Hot-reload without restart** — the memory backend is treated as a plugin, not a singleton. When settings change, the new backend activates without touching in-flight sessions.
- **Per-agent or shared stores** — memory scope is a first-class setting, not global state.
- **Shadow mode for automatic recall** — new recall behavior starts silently (keyword scoring, logged but not surfaced) before fully enabling, letting operators validate quality before users see it.
- **Local Git checkpoints** — revisions, withdrawals, and merges are inspectable through versioned snapshots. Memory edits are auditable without a separate audit system.

### 2. Deep Research job resumption across Gateway restarts (2026.11.10)
Long-running investigation jobs (multi-source, multi-step) now survive Gateway restarts. The pattern: eligible jobs store enough state at each step that they can be re-enqueued on startup and continue from the last completed step rather than from scratch. Reports are retained for seven days with source citations preserved.

### 3. System-prompt caching on OpenAI routes (2026.10.34)
Added to the extended-stable release: when an OpenAI route is used, the provider now takes advantage of OpenAI's prompt caching. This is a low-effort, high-impact change — no model routing logic changes, only a flag in the provider call. Reduces token cost on repeated-system-prompt scenarios (e.g., always-on agents, heartbeat tasks).

### 4. Subagent answer persistence across restarts (2026.11.10-beta.3)
Completed sub-agent answers are written to durable state so they survive a runtime restart. This complements the Deep Research resumption pattern and signals a broader move: treat completed work as committed state, not ephemeral in-memory results.

### 5. Memory compaction tied to conversation size (2026.11.10-beta.3)
Reduced memory use when compacting or opening large conversations. Signals a pressure-based, lazy compaction strategy rather than fixed-interval compaction.

---

## What we can use in Lexicon

Ranked by value / effort (HIGH → LOW for value; LOW → HIGH for effort = higher priority):

### Spike 1 — System-prompt caching on OpenAI routes ★★★ value / ★ effort
**File:** `src/engine/llm/openai_provider.py`

The OpenAI API supports prompt caching for repeated prefixes. Lexicon's `openai_provider.py` makes the API calls; adding `cache_control` to system-message blocks (or enabling the `store: true` / `seed` approach for caching-eligible calls) is a small code change with immediate token-cost reduction for agents that run with stable system prompts (heartbeat tasks, always-on agents).

### Spike 2 — Agent job resumption across restarts ★★★ value / ★★ effort
**Files:** `src/engine/runner.py`, `src/engine/queue.py`

Lexicon's runner and queue manage agent jobs in memory. The pattern from OpenClaw 2026.11.10: serialize enough job state at each logical step (not every tick) so jobs can be re-enqueued on startup. The implementation needs: (a) a persistent job-state store alongside the existing queue, (b) a startup reconciliation pass that re-enqueues incomplete jobs, (c) idempotent step logic so replaying a step from last checkpoint doesn't double-apply side effects.

### Spike 3 — Memory shadow mode / gradual recall ★★ value / ★ effort
**Files:** `src/engine/memory/manager.py`, `src/engine/context/pruner.py`

The shadow-mode pattern (run new logic, log results, surface nothing to user) is a low-cost way to safely roll out changes to memory recall in Lexicon. The `manager.py` already coordinates recall; adding a `shadow: bool` flag that logs recall results to a separate trace without injecting them into context would let us validate recall quality on live traffic before enabling it.

### Spike 4 — Pluggable memory with hot-reload ★★ value / ★★★ effort
**Files:** `src/engine/memory/manager.py`, `src/engine/memory/episodic.py`, `src/engine/memory/working.py`

Lexicon's memory is currently wired at startup. Extracting the memory backend behind an interface (like OpenClaw's `plugins.slots.memory`) and hot-reloading on config change would let operators swap memory backends (e.g., episodic → knowledge-vault) without restarting the engine. High-effort but architecturally significant.

### Spike 5 — Per-job result persistence ★★ value / ★★ effort
**Files:** `src/engine/memory/episodic.py`, `src/engine/runner.py`

Completed agent job outputs should be written to episodic memory as immutable records (like Git commits — once written, referenced but not rewritten). This aligns with the OpenClaw subagent-answer-persistence pattern and makes job outputs available to future sessions without keeping the runtime alive.

---

## My picks for what to spike next

1. **Spike 1 (OpenAI prompt caching)** — ship in a day, pays for itself in token costs. Touch only `src/engine/llm/openai_provider.py`.
2. **Spike 3 (memory shadow mode)** — small delta to `src/engine/memory/manager.py`, meaningful for safely testing the memory changes coming in Spikes 4–5.
3. **Spike 2 (job resumption)** — the highest-impact reliability improvement; worth a focused sprint after shadow mode is in.
