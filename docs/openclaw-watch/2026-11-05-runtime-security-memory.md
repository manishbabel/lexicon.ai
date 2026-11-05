# OpenClaw Watch — 2026-11-05: Runtime, Security & Memory

**Digest period:** 2026-05-27 → 2026-11-05  
**Lexicon last check:** 2026-09-23 (previous run found no accessible sources; no digest written)  
**Sources:** github.com/openclaw/openclaw/releases (primary), WebSearch synthesis

---

## What shipped

Five releases are new since the 2026.5.27 baseline. Only the ones with architectural signal are detailed below; pure-dep or hotfix point releases are noted but skipped.

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.11.1 | 05 Nov | **Latest stable** | Subagent follow-up improvements, provider rate-limit handling, channel reliability (Telegram/Discord/webhook), interruption recovery |
| 2026.11.5-beta.1 | 04 Nov | Pre-release | PostgreSQL data plane, Knowledge Scribes, PR-from-chat workflows, cross-device/cloud execution, decision + media model routing, plugin upgrades, backup/upgrade safety |
| 2026.10.10 | 03 Nov | Stable | Maintenance; no headline pattern changes in release notes |
| 2026.10.10-beta.5 | 30 Oct | Pre-release | Gateway streaming stall fixes, cron catch-up fixes, security boundary hardening, terminal output escaping |
| 2026.9.36 | 29 Oct | Extended-stable (LTS) | Fail-closed allowlists, workspace-only tool-permission derivation, bounded untrusted-input parsing, certificate trust hardening |

---

## What's notable

### 1. PostgreSQL durable memory plane (2026.11.5-beta.1)
OpenClaw introduced a PostgreSQL backend as an alternative to its default file-local JSONL stores. The pattern: a backend-agnostic `MemoryBackend` interface (read/write/search) with JSONL and Postgres implementations selectable via config. Memory layers (short-term, episodic) stay structurally identical; only the persistence driver swaps. Enables multi-process access, durable restarts, and SQL-native querying of episodic records.

### 2. Fail-closed tool permission derivation (2026.9.36)
Two changes together: (a) a `tools.fs.workspaceOnly` flag that restricts delegated/Gateway-built tools to the agent's workspace, requiring explicit approval for any path outside it; (b) unresolved name-keyed `allowFrom` entries now grant nothing (fail-closed) rather than admitting all callers. The prior behaviour was fail-open—a missing entry effectively bypassed the check.

### 3. Provider rate-limit handling (2026.11.1)
Automatic detection of 429/rate-limit responses at the LLM provider layer, with exponential backoff and optional fallback to a secondary provider. Applied in the provider base class so all concrete implementations get it for free.

### 4. Bounded untrusted-input parsing (2026.9.36)
Hard limits on parsing external payloads: TOML key count, URI length, collection sizes in schemas, media metadata. Limits are applied at the ingestion boundary (before deserialization) rather than after. The principle: reject oversized external data structurally before it reaches the agent's logic.

### 5. Cron catch-up avoidance (2026.10.10-beta.5)
When the scheduler wakes after downtime it now skips missed fires instead of replaying them all at once (the classic "thundering herd on restart"). The fix: compare last-fired timestamp to now; if the gap exceeds one interval, mark the job as caught-up without firing and resume normally.

---

## What we can use in Lexicon

> All file paths verified to exist under `src/`.

| # | Pattern | Value | Effort | Lexicon target(s) |
|---|---|---|---|---|
| 1 | Provider rate-limit backoff | **High** | **Low** | `src/engine/llm/provider.py`, `src/engine/llm/router.py` |
| 2 | Fail-closed tool permissions | **High** | **Low** | `src/engine/tools/registry.py` |
| 3 | Bounded untrusted-input parsing | High | Medium | `src/gateway/protocol.py` |
| 4 | Cron catch-up avoidance | Medium | Low | `src/cron/scheduler.py`, `src/cron/store.py` |
| 5 | PostgreSQL durable memory backend | Medium | High | `src/engine/memory/manager.py`, `src/engine/memory/short_term.py`, `src/engine/memory/episodic.py` |

**Detail on the top two:**

**#1 — Provider rate-limit backoff.** `LLMProvider.stream()` and `LLMProvider.complete()` in `src/engine/llm/provider.py` are abstract with no retry logic. Add a decorator or mixin in the base class that catches 429/`RateLimitError` and retries with jitter (suggested: 1s, 2s, 4s, max 3 retries). The `PersonaLLMRouter` in `src/engine/llm/router.py` could then route to a fallback provider if all retries exhaust. Zero impact on callers—`AgentRuntime` calls the same `stream()` interface.

**#2 — Fail-closed tool permissions.** `ToolDef` in `src/engine/tools/registry.py` has no scope field. Add `workspace_only: bool = False` to the dataclass. In `wire_into_runtime()`, if the runtime is flagged as untrusted, skip tools where `workspace_only=False` or require an explicit approval callback. The fail-closed analogue: unregistered tools grant nothing, not everything.

**#5 — PostgreSQL memory.** `ShortTermMemory` and `EpisodicMemory` write to JSONL today. The `MemoryManager` constructs them directly in `__init__`. Abstracting the backend would require: a `MemoryBackend` protocol, two implementations (JSONL, Postgres), and a config key. Medium effort because JSONL search is currently in-process; Postgres would need pgvector or an equivalent for the similarity queries in `src/engine/memory/search.py`.

---

## My picks for what to spike next

**Spike 1 (this week): Provider rate-limit backoff** — `src/engine/llm/provider.py` is a clean 44-line abstract base. Adding backoff is a low-risk, isolated change that immediately improves resilience for any persona hitting Claude or OpenAI rate limits in production.

**Spike 2 (after Spike 1): Fail-closed tool permissions** — `ToolDef` in `src/engine/tools/registry.py` is a simple dataclass. A `workspace_only` field plus a check in `wire_into_runtime()` aligns Lexicon with OpenClaw's security posture without touching any tool implementations.

---

*Sources: [github.com/openclaw/openclaw/releases](https://github.com/openclaw/openclaw/releases) (primary). Third-party changelog aggregators (patchbot.io, gradually.ai, betterclaw.io) were outside this session's allowed network domains and could not be verified.*
