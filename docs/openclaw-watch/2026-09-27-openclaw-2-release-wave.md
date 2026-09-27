# OpenClaw Release Watch — 2026-09-27

**Digest period:** 2026.5.27 (stable) → 2026.9.6  
**Digest type:** Major release wave — pattern-worthy

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.7.35** | 2026-09-21 | Extended-stable (LTS) | Security hardening, channel message integrity, bounded resource lifecycles |
| **2026.8.1** | 2026-08-30 | Major — "OpenClaw 2.0" | Largest release in project history (~17k PRs, 933 contributors). Runtime, memory, skills, gateway, security overhaul |
| **2026.9.5** | 2026-09-19 | Stable | Infrastructure, stability (no new architectural patterns) |
| **2026.9.6** | 2026-09-23 | Stable | macOS launch-crash fix for 2026.9.6 original build |

**Latest stable:** 2026.9.6  
**Latest beta:** not determined from available sources (secondary docs blocked by network policy)

---

## What's notable

### 1. Memory Ownership and Source Provenance (2026.8.1)
OpenClaw added per-session memory attribution: users can inspect which sessions contributed to stored memory, exclude specific sources from admission, and selectively forget derived memory. This is a step beyond write-and-read memory — it makes memory **auditable and controllable**. The pattern pairs a source-tagged write path with a query-time filter and a targeted delete API.

### 2. CPU-Scaled Agent Concurrency with Hard Bounds (2026.8.1)
Default top-level agent concurrency is now derived from `os.cpu_count()`, bounded to [8, 16]. Previously it was a static constant. The pattern: compute a sensible default at startup from available parallelism rather than baking in a number, while capping the upper bound to prevent memory pressure. Low implementation cost; meaningfully improves throughput on bigger hosts.

### 3. Private Credential Requests — Masked Prompt in Chat (2026.8.1)
An agent can now request a credential through a masked terminal/UI prompt without ever emitting the value into the conversation transcript. The pattern: a `credential_request` signal from the engine to the gateway, which opens a secure input channel and returns only an opaque handle. The credential never touches the message log. This is qualitatively different from reading env vars — it enables interactive credential injection mid-run.

### 4. Protected Egress on Run Termination (2026.8.1)
When a run ends (success, cancellation, or error), OpenClaw now explicitly closes proxy connections, upstream provider requests, and bypass tunnels associated with that run. Replacement runs cannot revive stale connections. The pattern: each run holds a lifecycle context that owns its external connections; teardown is part of the run's exit protocol, not left to GC or OS cleanup. Prevents credential/token leaks across runs.

### 5. Command Injection Hardening at the Parse Layer (2026.7.35)
The gateway rejects escaped-newline command words, mismatched origin headers, and injected option arguments (e.g., Git flag injection) at parse time — before they reach the execution layer. The pattern: input validation as a parse-layer responsibility, not a semantic-layer responsibility. Cheaper and more reliable than trying to sanitize after interpretation.

---

## What we can use in Lexicon

Ranked by (value × effort⁻¹). All file paths verified to exist.

### 🔴 Spike: Memory Ownership — `src/engine/memory/manager.py` + `src/engine/memory/episodic.py`
**Value: High | Effort: Medium**

Lexicon's `manager.py` writes episodic memories without tagging which session they came from. Adding a `source_session_id` field to episodic records (`episodic.py`) and a `forget_by_source()` method to the manager would match OpenClaw's pattern. The `transcript_index.py` already indexes by session — it's the natural provenance carrier. User benefit: "forget what you learned in the meeting on Monday" becomes a targeted delete, not a full wipe.

**Files:** `src/engine/memory/manager.py`, `src/engine/memory/episodic.py`, `src/engine/memory/transcript_index.py`

---

### 🔴 Spike: Private Credential Requests — `src/gateway/protocol.py` + `src/engine/runtime.py`
**Value: High | Effort: Low**

`src/gateway/protocol.py` defines the message types between gateway and engine. Adding a `CredentialRequest` message type and a masked-input handler in `src/gateway/server.py` mirrors the OpenClaw pattern. The engine side emits the signal from `runtime.py`; the gateway handles the secure prompt and returns an opaque token. Nothing changes in the conversation log. This directly hardens the `src/vault/reader.py` and `src/vault/writer.py` paths where credentials may currently flow through unmasked.

**Files:** `src/gateway/protocol.py`, `src/gateway/server.py`, `src/engine/runtime.py`, `src/vault/reader.py`

---

### 🟡 Port: CPU-Scaled Concurrency — `src/engine/runtime.py` + `src/engine/queue.py`
**Value: High | Effort: Low**

Replace whatever static concurrency ceiling is in `src/engine/runtime.py` or `src/engine/queue.py` with `min(max(os.cpu_count() or 1, 8), 16)`. One-line change with measurable throughput upside on the dev machine vs. a cloud host. No architectural risk.

**Files:** `src/engine/runtime.py`, `src/engine/queue.py`

---

### 🟡 Port: Protected Egress on Run Exit — `src/engine/runner.py` + `src/gateway/session.py`
**Value: High | Effort: Medium**

`src/engine/runner.py` is the per-run entry point. Adding a context manager that tracks outbound HTTP sessions (to `src/engine/llm/provider.py` providers, to `src/engine/tools/web_search.py`, etc.) and explicitly cancels them on exit prevents orphaned connections. `src/gateway/session.py` owns the per-session lifetime and is the right place to enforce that a closed session cannot reuse a prior run's connections.

**Files:** `src/engine/runner.py`, `src/gateway/session.py`, `src/engine/llm/provider.py`

---

### 🟢 Consider: Bounded Request Lifecycles — `src/engine/context/pruner.py` + `src/engine/queue.py`
**Value: Medium | Effort: Medium**

OpenClaw 2026.7.35 introduced explicit timeouts and cancellation for catalog lookups, history fetches, and provider waits. Lexicon's `src/engine/context/pruner.py` and `src/engine/queue.py` likely lack per-operation timeouts. Adding bounded `asyncio.wait_for` wrappers (with configurable timeouts from `src/shared/config.py`) on LLM, memory search, and tool calls would prevent single slow operations from hanging the whole run.

**Files:** `src/engine/context/pruner.py`, `src/engine/queue.py`, `src/shared/config.py`

---

### 🟢 Consider: Heartbeat Owner Routing — `src/cron/scheduler.py`
**Value: Medium | Effort: Low**

OpenClaw's pattern: if a scheduled heartbeat can't resolve a delivery target, skip the poll rather than firing into void or crashing. In Lexicon, `src/cron/scheduler.py` runs automations — adding a pre-flight owner-resolvability check before dispatch avoids silent failures in headless/daemon modes.

**Files:** `src/cron/scheduler.py`, `src/cron/store.py`

---

## My picks for what to spike next

1. **Memory ownership** (`src/engine/memory/`) — the provenance model is foundational; once in place, "forget session X" and user-controlled memory audit become trivial to expose. Low coordination cost, high user-facing payoff.

2. **Private credential requests** (`src/gateway/protocol.py`) — one new message type, one masked-input handler. Prevents credential values from ever appearing in transcript logs, which matters increasingly as Lexicon sessions get persisted.

3. **CPU-scaled concurrency** (`src/engine/runtime.py`) — one-liner. Do it alongside the next unrelated PR to get the improvement for free.
