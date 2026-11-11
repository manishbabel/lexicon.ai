# OpenClaw Watch — 2026-11-11 Digest

**Coverage:** 2026.6.1 through 2026.11.3 (stable) and 2026.11.5-beta.1 (beta)
**Previous baseline:** 2026.5.27 stable / 2026.5.28-beta.2 beta (last checked 2026-09-23)

---

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.6.1 | 03 Jun | stable | Resilient agent and Codex runs; hosted push relay defaults |
| 2026.7.1 | 13 Jul | stable | Control UI overhaul; GPT-5.6 compatibility; iOS/Android/macOS updates |
| 2026.9.5 | 19 Sep | stable | 64 commits; broad runtime and channel reliability fixes |
| 2026.9.37 | 10 Nov | gateway-only extended-stable | Critical security/reliability backport from retired 2026.9.x line |
| 2026.10.3 | 13 Oct | stable | 90 commits, 79 PRs, 99 contributors; reliability hardening |
| 2026.11.1 | 05 Nov | stable | Mac settings safety; channel reconnects; provider rate-limit respect |
| 2026.11.2 | 08 Nov | stable | 166 commits, 113 PRs, 64 contributors |
| **2026.11.3** | **10 Nov** | **stable (latest)** | Subagent isolation; task handoff; tool failure reporting; security hardening |
| 2026.11.5-beta.1 | 04 Nov | pre-release | Knowledge Scribes; PostgreSQL data plane; PR-from-chat; cross-device execution |

Sources: [github.com/openclaw/openclaw/releases](https://github.com/openclaw/openclaw/releases)

---

## What's Notable

### 1. Subagent result isolation from streamed replies (2026.11.3)
Private subagent outputs are explicitly stripped before streaming to the outer conversation. This is a correctness+security pattern: a child agent's intermediate reasoning or sensitive tool output must not leak into the parent's reply stream. OpenClaw wires this at the orchestrator layer, not at the LLM provider layer.

### 2. Tool failure reporting — no silent success (2026.11.3)
When a tool call goes unanswered (timeout, missing handler, refused), the runtime now surfaces it as an error rather than allowing the turn to end as successful. Prior to this, callers had no reliable signal that a tool invocation was dropped. The fix lives in the agent runner loop.

### 3. Provider rate-limit backoff respects Retry-After (2026.11.1)
Provider recovery now reads provider-specified rate-limit timing (e.g. `Retry-After` header or response body field) instead of using a fixed backoff. This shrinks unnecessary wait time under real-world quota constraints and avoids premature retry storms.

### 4. Knowledge Scribes — reusable capture workflows (2026.11.5-beta.1)
A new memory abstraction that wraps knowledge capture in a reusable "scribe" workflow: the agent can invoke a named scribe to extract, format, and persist a structured knowledge artifact from an interaction. It sits above raw episodic memory and below full skill execution.

### 5. PostgreSQL data plane with migration tooling (2026.11.5-beta.1)
State storage now has a first-class PostgreSQL backend with schema migration coverage. Noteworthy because OpenClaw had shipped with an in-process SQLite default; the Postgres path unlocks multi-node deployments and persistent ephemeral sessions without external infrastructure changes.

---

## What We Can Use in Lexicon

Ranked by value/effort. Each maps to a file verified to exist in `src/`.

| # | Pattern | Value | Effort | File(s) |
|---|---|---|---|---|
| 1 | **Tool failure reporting** — surface dropped/unanswered tool calls as errors, not silent success | High | Low | `src/engine/runner.py`, `src/engine/tools/registry.py` |
| 2 | **Provider Retry-After backoff** — read provider-specified rate-limit timing in retry logic | High | Low | `src/engine/llm/provider.py`, `src/engine/llm/router.py` |
| 3 | **Subagent result isolation** — strip child agent outputs from parent reply stream | High | Medium | `src/engine/orchestrator.py`, `src/engine/runner.py` |
| 4 | **Parent→child task handoff after cancel** — reassign work when a child task is cancelled mid-flight | Medium | Medium | `src/engine/orchestrator.py`, `src/engine/queue.py` |
| 5 | **Credential isolation in child-process environments** — prevent credential inheritance across process boundaries | High | Medium | `src/engine/runtime.py` |
| 6 | **Knowledge Scribes** — named, reusable memory-capture workflows triggered from the agent loop | Medium | High | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py`, `src/engine/skills.py` |
| 7 | **PostgreSQL data plane** — persistent, multi-node state store with migration tooling | Low-now / High-later | High | `src/engine/memory/`, `src/feedback/db.py` |

---

## My Picks for Next Spikes

**Spike 1 (this week): Tool failure reporting** (`src/engine/runner.py`)
Currently the runner loop can silently absorb a missing tool response. Add an explicit check after `tool_call` dispatch: if the result is absent or the registry has no handler, raise/return a typed `ToolCallFailed` event instead of continuing the turn. Low blast radius, immediate correctness improvement.

**Spike 2 (this week): Provider Retry-After** (`src/engine/llm/provider.py`)
Check for a `retry_after` field or `Retry-After` header in the rate-limit exception path of each provider (`claude_provider.py`, `openai_provider.py`, `litellm_provider.py`). Use it as the floor for the next retry delay. Prevents the current fixed-backoff from either retrying too fast (429 storm) or waiting longer than needed.

**Spike 3 (next sprint): Subagent result isolation** (`src/engine/orchestrator.py`)
Audit `orchestrator.py`'s stream-merging path to confirm child agent `tool_result` and `thinking` blocks are gated before being forwarded to the outer session. If not gated, add a filter stage at the merge boundary.
