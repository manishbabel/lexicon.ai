# OpenClaw Watch — 2026-09-14

**Baseline:** 2026.5.27 stable / 2026.5.28-beta.2  
**This digest covers:** 2026.6.35 LTS · 2026.9.3 · 2026.9.4 stable / 2026.9.1-beta.1

---

## What shipped

### 2026.9.4 (Sep 11, 2026) — latest stable
Validation pass across npm, Docker, and native platforms; checksummed Linux desktop packages (AppImage + Debian). Primarily a distribution/CI hardening release; no new runtime patterns.

### 2026.6.35 (Sep 10, 2026) — June 2026 LTS final
Security-focused maintenance release for the LTS line.

- **Safer provider and channel boundaries.** Bundled providers and channel adapters now bound untrusted response bodies, reject oversized inputs before any expensive work begins, and recover safely when transports fail mid-stream.
- **More reliable long-running delivery.** Agent, gateway, retry, and channel paths handle cancellation, retries, partial sends, and process-stream failures without losing work or replaying operations.

### 2026.9.3 (Sep 8, 2026) — stable
Large feature release (1,844 PRs, 190 contributors).

- **Isolated candidate state validation.** Core and plugin changes are rehearsed in an isolated candidate before activation; supports eligible 2026.9.2 migrations and recovers abandoned update records without interrupting a healthy Gateway.
- **Prompt cache preservation + memory search optimisation.** Runtime keeps warm prompt caches across cold session updates; reduces redundant work during memory search; reuses worker builds between sessions.
- **Persistent agent-owned skill collections.** Skills live in a single cross-workspace collection per agent, with full instruction diff views and safer Doctor-driven retirement of stale drafts.

### 2026.9.1-beta.1 — latest beta
Preview of 2026.9.x forthcoming features; details not yet stable.

---

## What's notable

1. **Untrusted response bounding at the provider layer** — response body limits and oversized-input rejection happen before expensive work (tokenisation, routing, memory writes). This is a defence-in-depth layer that Lexicon's LLM providers currently lack.

2. **Delivery atomicity in gateway + agent paths** — partial-send and process-stream failure recovery ensures long-running tasks don't silently lose progress or replay side-effectful operations on reconnect. Critical for multi-turn agent runs.

3. **Isolated state rehearsal for runtime updates** — applying candidate state in isolation before committing avoids corrupt in-flight runs during deploys. Directly relevant to Lexicon's hot-reload use case.

4. **Cold-session memory search deduplication** — skipping redundant index sweeps during session cold-start is a targeted perf win with no behavioural change; easy to adopt.

5. **Persistent, diffable skill collections** — agent-scoped skill state that survives workspace switches and shows instruction diffs before edits reduces skill drift in long-lived agents.

---

## What we can use in Lexicon

Ranked by value/effort (high value first, lower effort preferred).

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---------|-------|--------|-----------------|
| 1 | **Bound untrusted LLM response bodies + reject oversized inputs pre-tokenise** | High | Low | `src/engine/llm/provider.py`, `src/engine/llm/router.py` |
| 2 | **Cold-session memory search dedup** | Medium | Low | `src/engine/memory/search.py` |
| 3 | **Gateway + agent delivery atomicity (partial-send + stream-failure recovery)** | High | Medium | `src/engine/runner.py`, `src/gateway/session.py` |
| 4 | **Warm prompt cache preservation across cold reloads** | Medium | Medium | `src/engine/llm/claude_provider.py`, `src/engine/llm/litellm_provider.py` |
| 5 | **Isolated candidate state for runtime updates** | High | High | `src/engine/runtime.py`, `src/engine/registry.py` |
| 6 | **Persistent agent-owned skill collections with diff view** | Medium | High | `src/engine/skills.py` |

---

## My picks for what to spike next

**Spike 1 (this week): Response body bounding in `src/engine/llm/provider.py`**  
Add a `max_response_bytes` guard in the base provider before any downstream parsing. Low-risk, directly hardens against prompt-injection-via-oversized-response. One-file change.

**Spike 2 (this sprint): Delivery atomicity in `src/engine/runner.py`**  
Wire cancellation tokens and partial-send checkpoints into the agent run loop so that stream interruptions and gateway reconnects don't replay tool calls. This pairs with the partial-send recovery OpenClaw added to its gateway session layer — worth looking at `src/gateway/session.py` in tandem.
