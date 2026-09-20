# OpenClaw Watch — 2026-09-20

## What shipped

| Version | Date | Type | Headline |
|---------|------|------|---------|
| **2026.8.1** (OpenClaw 2.0) | 2026-08-30 | Stable | Mega-release: sessions, security, memory, compaction, concurrency, credentials, 15+ channels |
| 2026.9.4 | 2026-09-11 | Stable | Reliability pass — input validation, build pipeline, upgrade-baseline testing |
| **2026.9.5** | 2026-09-19 | Stable (latest) | 64 direct commits, recovery for provider boundaries and long-running delivery |
| 2026.6.35 | 2026-09-10 | LTS (final) | Extended-Stable / LTS close-out; bundled-adapter safety, workspace input validation |

Baseline was `2026.5.27` (stable) / `2026.5.28-beta.2` (beta). All four releases are new.
No new beta track was identified; 2026.9.1-beta.1 was a mislabeled duplicate of 2026.8.1-beta.4.

---

## What's notable

### 1 — Memory provenance labels (2026.8.1)
OpenClaw introduced a `source` + `confirmed` flag on every memory entry: values are
`user`, `model`, or `tool`, and `confirmed: bool` marks whether a human explicitly
ratified the entry. At retrieval time the agent surfaces this metadata so it can
distinguish "user told me X" from "I inferred X." The explicit goal is preventing
long-running agents from accumulating low-confidence inferences into "memory sludge"
that quietly steers future responses.

### 2 — Provider-managed context compaction (2026.8.1)
Anthropic and xAI both now support server-side compaction: rather than the client
sending a summarization prompt and replacing old messages locally, the provider
handles the compaction and returns a compact representation, while the local
transcript remains intact and unsummarized. OpenClaw wires this in as a short-circuit
in its compactor: if the provider is Anthropic/xAI and the context hits the threshold,
delegate to the provider API instead of running the local LLM-summarization pass.

### 3 — CPU-scaled default concurrency (2026.8.1)
OpenClaw sizes top-level agent concurrency at startup from `cpu_count()` (range 8–16),
replacing a hardcoded constant. Explicit operator limits are still respected as a
ceiling. On low-end hardware this avoids starving the machine; on high-core servers
it unlocks throughput automatically.

### 4 — Conversation-bound automation contexts (2026.8.1)
When a cron or agent-turn automation is created inside a session, OpenClaw now records
the originating `conversation_id` and binds the automation to that conversation by
default. Context-free creations (e.g. via CLI) remain isolated. This means follow-up
runs of a recurring task post output back to the conversation that spawned them rather
than to a detached log.

### 5 — Database integrity hardening (2026.8.1 + 2026.9.x)
WAL split-brain corruption prevention (separate-process snapshot verification; rollback
journaling on virtiofs/9p mounts; schema-version rejection before restart loops);
extended in 2026.9.x to cover more provider boundary recovery. Relevant wherever
SQLite is used for durable state.

---

## What we can use in Lexicon

Ranked by value × ease (highest first). All file paths verified to exist.

### #1 — Provider-managed compaction  `HIGH value / LOW effort`
**Files:** `src/engine/context/compactor.py`, `src/engine/llm/claude_provider.py`

Lexicon already has LLM-based summarization compaction at `src/engine/context/compactor.py`
(runs after pruning; strips tool-result details; replaces old messages with a digest).
OpenClaw 2.0 adds a provider short-circuit: when the active provider is Anthropic,
skip the local summarization pass and instead pass the context window to the API with
the compaction beta header, receiving back a minimal context that the provider already
optimized. The local full transcript is preserved separately.

Spike: add a `try_provider_compaction(messages, budget)` method to `claude_provider.py`
that calls the Anthropic API compaction endpoint; have `compactor.py` call it first and
fall back to the local LLM pass on failure or non-Anthropic provider.

### #2 — Memory provenance labels  `HIGH value / MEDIUM effort`
**Files:** `src/engine/memory/episodic.py`, `src/engine/memory/manager.py`

`EpisodicEntry` currently has `type` (transcript / suggestion / tool_call / decision /
note) but no provenance dimension. Add two fields:
- `source: Literal["user", "model", "tool"]`
- `confirmed: bool = False`

`manager.py` should surface `confirmed=False` entries with lower weight in retrieval
ranking, and agents should be able to call a `confirm_entry(id)` tool to promote an
inferred memory. This directly addresses the "memory sludge" risk for long-running
Lexicon agents (ai-educator, chief, software-engineer workspaces).

### #3 — CPU-scaled concurrency  `MEDIUM value / LOW effort`
**Files:** `src/engine/runner.py`, `src/engine/queue.py`

Replace any hardcoded concurrency constant with `min(max(os.cpu_count() or 4, 8), 16)`,
with an explicit operator-override path. One-line change with a meaningful effect on
multi-agent sessions.

### #4 — Conversation-bound automation contexts  `MEDIUM value / MEDIUM effort`
**Files:** `src/cron/scheduler.py`, `src/cron/defaults.py`

When `scheduler.py` creates a recurring job inside a live session, record the
`session_id` / `conversation_id` at job creation time and restore it on each firing.
Currently scheduled jobs run in an isolated context; binding them to the originating
conversation lets follow-up runs surface results back into the chat they came from.

### #5 — SQLite WAL integrity (snapshot verification)  `MEDIUM value / HIGH effort`
**Files:** `src/engine/memory/manager.py`, `src/cron/store.py`

Adopt OpenClaw's pattern of separate-process snapshot integrity checks before
restoring; switch to rollback journaling where mounts may not support WAL. Lower
priority — only critical if agents run on network/virtiofs mounts.

---

## Spikes for next cycle

1. **Provider-managed compaction** (1–2 days) — highest ROI. Lexicon's compactor
   scaffold is already there; the spike is purely additive. Target:
   `src/engine/context/compactor.py` + `src/engine/llm/claude_provider.py`.

2. **Memory provenance labels** (0.5 days to add fields + 1 day for manager changes)
   — prevents sludge accumulation in the three agent workspaces. Start with
   `EpisodicEntry` in `src/engine/memory/episodic.py`.
