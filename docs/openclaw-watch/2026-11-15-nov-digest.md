# OpenClaw Watch — 2026-11-15 Digest

**Previous check:** 2026-09-23 (stable 2026.5.27 / beta 2026.5.28-beta.2)
**This check:** 2026-11-15 (stable 2026.11.3 / beta 2026.11.5-beta.3)

---

## What Shipped

A lot moved since the September baseline. The headline milestone is **OpenClaw 2.0 (2026.8.1)**, which rebuilt memory, sessions, and the agent runtime. The November patch train then hardened the runtime around task lifecycle, tool failure visibility, and credential hygiene. Only pattern-bearing releases are detailed below; dep bumps and hotfixes are omitted.

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.8.1 | ~Aug 2026 | Stable | OpenClaw 2.0 — memory consolidation, session branching, credential proxy |
| 2026.9.37 | 10 Nov | Extended-stable (LTS) | Critical security + reliability backport line |
| 2026.11.1 | 5 Nov | Stable | Gateway auth preservation, secrets-safe config saves |
| 2026.11.2 | 5 Nov | Stable | Mac settings + Claude CLI handling fixes |
| 2026.11.3 | 10 Nov | Stable (Latest) | Task cancellation/handoff, silent-success elimination, credential isolation |
| 2026.11.5-beta.2 | 12 Nov | Beta | URI validation, oversized-collection rejection, bi-directional pagination |
| 2026.11.5-beta.3 | 15 Nov | Beta | Bounded memory compaction, configurable summary limits, restart recovery |

---

## What's Notable (Patterns)

### 1. Task Cancellation → Handoff (2026.11.3)
A parent agent can now hand off to replacement work _after_ cancelling a child task. Previously, cancel was terminal — the parent had to start fresh. The new pattern treats cancel as a lifecycle event that the parent can observe and pivot on, not a final error.

### 2. Silent-Success Elimination for Tool Failures (2026.11.3)
Unanswered tool failures that previously caused a turn to end as a success are now surfaced to the caller. This is an observability inversion: failure is explicit by default, not absorbed.

### 3. Bounded Memory Compaction with Configurable Limits (2026.11.5-beta.3)
Transcript indexing, trimming, and compaction now run under configurable memory ceilings. Summary depth is capped per session. This prevents compaction from becoming an unbounded background consumer as transcripts grow.

### 4. Credential Reference / Resolved Value Separation (2026.8.1)
The runtime now distinguishes a _reference_ to a secret (the name/path) from the _resolved value_. References are safe to pass through model context and logs; resolution happens only at the execution boundary, through an opt-in proxy that limits substitution to approved destinations.

### 5. URI Validation + Oversized Collection Early Rejection (2026.11.5-beta.2)
Incoming identifiers are validated with a fast-URI library before they reach routing. Oversized collections are rejected at ingestion rather than failing deep in processing. Both are early-rejection patterns that keep malformed input from propagating.

---

## What We Can Use in Lexicon

Ranked by value/effort ratio (high value first, easier lifts higher within same value tier):

### Tier 1 — High value, moderate effort

**A. Silent-success elimination in the tool runner**
- File: `src/engine/runner.py`
- The runner currently completes a turn even when a tool call receives no answer. Add an explicit check: if any dispatched tool call has no response by turn-end, raise or log a named failure rather than returning success. This is a correctness fix — it prevents silent drops in multi-tool turns.
- Effort: ~1 day

**B. Task cancellation + handoff in the orchestrator**
- File: `src/engine/orchestrator.py`
- Orchestrator cancel today terminates downstream work. Add a callback/hook point post-cancel that the calling context can use to enqueue replacement work. Pairs with `src/engine/queue.py` for the replacement dispatch.
- Effort: ~2 days

### Tier 2 — High value, higher effort

**C. Credential reference/value separation in vault tooling**
- Files: `src/engine/tools/vault_read.py`, `src/engine/tools/vault_write.py`
- Vault tools today may resolve secrets before they reach the LLM provider layer. Introduce a two-phase pattern: tools return a reference handle; resolution only happens in `src/engine/llm/provider.py` immediately before the API call, never in model context or logs.
- Effort: ~3 days

**D. Bounded compaction with configurable depth**
- Files: `src/engine/context/compactor.py`, `src/engine/context/pruner.py`
- Add a `max_summary_depth` / `max_compaction_tokens` config knob to `src/shared/config.py` and thread it through the compactor. Prevents compaction from consuming unbounded memory on long-running sessions.
- Effort: ~2 days

### Tier 3 — Defensive hygiene, low effort

**E. URI validation at gateway ingress**
- File: `src/gateway/protocol.py`
- Add early validation of URI/identifier fields in incoming protocol messages before they reach the router. Reject malformed or oversized payloads at the boundary. Can be a simple regex or library check.
- Effort: ~half day

---

## Picks for What to Spike Next

1. **Spike A first** (silent-success elimination in `runner.py`): it's a correctness bug with no downside — a strict improvement. Low effort, immediate observability win.
2. **Then Spike C** (credential ref/value separation): Lexicon's vault tools are the highest-risk surface for secret leakage into model context. The OpenClaw pattern is well-defined and directly applicable.
3. **Watch 2026.11.5 stable** when it graduates from beta — the memory compaction limits (Spike D) will have more validated defaults from production usage by then.
