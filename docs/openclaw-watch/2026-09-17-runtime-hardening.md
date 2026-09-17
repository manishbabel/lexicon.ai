# OpenClaw Watch — 2026-09-17: Runtime Hardening & Skill Collections

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.9.4** | 2026-09-11 | Stable | 20 direct commits; platform verification pass (npm, Docker, macOS, Linux AppImage/Debian) |
| **2026.9.3** | 2026-09-08 | Stable | Isolated candidate state for updates; warm prompt-cache preservation; agent-owned Skill Workshop collections |
| **2026.6.35** | 2026-09-10 | LTS (Extended Stable) | Final June-2026 LTS: safer provider/channel boundaries, cancellation handling throughout delivery stack, response memory-safety caps |
| 2026.8.1-beta.4 | Aug 2026 | Beta | Rolling beta stabilization |

Previous baseline: `2026.5.27` (stable) / `2026.5.28-beta.2`.

---

## What's notable

### 1 · Isolated candidate state before activation (2026.9.3)
Updates to core or plugins are now "rehearsed" inside a disposable copy of runtime state. The live runtime only swaps to the new state after the candidate is validated — a failed rehearsal leaves the live state untouched. This eliminates a class of half-applied-update crashes.

### 2 · Response body memory-safety caps (2026.6.35 LTS)
Both successful and error response reads are capped before the full body is buffered. A hostile or runaway payload can no longer exhaust process memory. The cap is applied at the provider/gateway boundary, not in application code.

### 3 · Cancellation propagation through the full delivery stack (2026.6.35 LTS)
`agent`, `gateway`, `retry`, and `channel` paths all handle cancellation uniformly. Previously each layer had ad-hoc cleanup; now a single cancel signal threads cleanly all the way down, preventing zombie jobs and leaked connections on long-running tasks.

### 4 · Warm prompt-cache preservation (2026.9.3)
Cold session start no longer reorders or repopulates cached prompt prefixes unnecessarily. The release calls out reducing "unnecessary work during cold session updates" — the concrete win is preserving the provider's prompt-cache hit rate across session restarts.

### 5 · Agent-owned skill collections (2026.9.3)
Skills are now owned by the agent (not the workspace). A single persistent collection travels with the agent identity across workspaces, so skill state survives workspace switches. The old per-workspace ownership model is deprecated.

---

## What we can use in Lexicon

Ranked by **value / effort** (H/M/L):

### A · Response-body size caps — `src/engine/llm/provider.py` · Value: H / Effort: L
`provider.py` is the shared base for all three LLM providers. Add a configurable `max_response_bytes` check when streaming/buffering responses; raise a typed `ResponseTooLargeError` instead of letting the buffer grow unbounded. Also apply in error-response handling (`src/engine/llm/claude_provider.py`, `openai_provider.py`, `litellm_provider.py`).

### B · Cancellation threading through cron/runner — `src/cron/scheduler.py` + `src/engine/runner.py` · Value: H / Effort: M
`scheduler.py` fires jobs and `runner.py` executes them, but neither currently propagates a cancel token end-to-end through to `src/gateway/server.py`. Model OpenClaw's pattern: a `CancellationToken` (or asyncio `Event`) is created at job-dispatch time, passed through the runner, and checked at each await point in the delivery path (`src/engine/queue.py` too).

### C · Isolated candidate state for hook/skill loading — `src/engine/runtime.py` · Value: M / Effort: M
When `runtime.py` loads or reloads hooks (`src/engine/hooks/loader.py`) or re-reads skills (`src/engine/skills.py`), do it against a scratch copy of the registry. Only commit the scratch copy to the live `registry.py` once all imports and validations pass. A bad skill file currently can leave the registry partially populated.

### D · Bounded text in memory search results — `src/engine/memory/search.py` · Value: M / Effort: L
Cap the `content` field returned per search hit at a configurable byte limit before it is handed back to the context. Mirrors OpenClaw's `details.content` bounded-text pattern and protects context-window accounting in `src/engine/context/token_counter.py`.

### E · Agent-scoped skill ownership — `src/engine/skills.py` + `workspaces/` · Value: M / Effort: H
Associating skill state with agent identity (e.g., keyed under workspace AGENT.md identity) rather than workspace directory would let skills like `workspaces/software-engineer/skills/knowledge-consolidator/SKILL.md` retain their persistent state when the agent is invoked from a different workspace. Design work required before spiking.

---

## My picks for what to spike next

1. **Response-body caps (A)** — one afternoon, directly hardens the provider boundary against misbehaving APIs, zero architectural risk.
2. **Bounded memory search (D)** — touches a single return path in `src/engine/memory/search.py`; closes a context-overflow path noticed during long sessions.
3. **Cancellation in cron/runner (B)** — medium effort but high payoff for Lexicon's cron-heavy workload (`src/cron/scheduler.py` runs heartbeats continuously); scope to cron → runner → queue before touching gateway.
