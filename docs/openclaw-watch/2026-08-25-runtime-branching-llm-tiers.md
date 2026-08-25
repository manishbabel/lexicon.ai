# OpenClaw Watch — 2026-08-25

**Tracked baseline:** 2026.5.27 (stable) / 2026.5.28-beta.2 (beta)
**Now at:** 2026.7.1-2 (stable) / 2026.8.1-beta.3 (beta)
**Source:** github.com/openclaw/openclaw/releases

---

## What shipped

| Version | Date | Channel | Headline |
|---|---|---|---|
| 2026.6.5 | Jun 5 | stable | Minor fixes, dep bumps |
| 2026.6.11 | Jun 11 | stable | Minor fixes |
| 2026.6.34 | Aug 8 | extended-stable | Security hardening: browser boundaries, agent resilience, channel recovery |
| 2026.7.1 | Jul 1 | stable | Memory startup repair, WSL state permissions, managed plugin update recovery |
| 2026.7.1-1 | Aug 4 | stable patch | Codex progress handling, plugin metadata compat |
| 2026.7.1-2 | Aug 4 | stable patch | Singleton-array metadata from newer npm clients |
| 2026.7.2-beta.7 | Aug 2 | beta | **Session branching/rewinding, MCP Apps + dashboards, structured question approvals, meeting integration (Teams/Zoom/Meet), local inference setup** |
| 2026.8.1-beta.2 | Aug 15 | beta | Secret egress host binding, GPT-5.6 model switching, SQLite snapshots, Fish Audio S2.1 streaming |
| 2026.8.1-beta.3 | Aug 24 | beta | **Multi-tier reasoning support (Sol/Terra/Luna/Ultra), Gateway lifecycle supervision, SQLite backup/restore, shared durable ingress monitors, Puppeteer CDP relay** |

Releases 2026.6.5 and 2026.6.11 are dep bumps / minor fixes — not ported below.

---

## What's notable (patterns worth studying)

### 1. Session branching and rewinding (2026.7.2-beta.7)

Users can fork or rewind a conversation from any prior message, switching between transcript branches. Sends queued against a branch remain safely deferred until the branch is active. OpenClaw stores branch metadata in its transcript index and rehydrates working memory from the chosen checkpoint.

This is the most structurally interesting pattern in this cycle: it separates the **transcript store** from the **active runtime**, creating a tree of message histories with a single hot branch at any time.

### 2. Structured question approvals with fair queuing (2026.7.2-beta.7)

Agents can emit a typed "question card" with enumerated options (not free text). The question surfaces across web/channel/native UIs as a tappable option row. Approvals (human-in-the-loop confirmations) get push notifications, a fair FIFO queue so no approval is starved, and a Claude tool-request relay so the agent can re-route follow-up work while waiting.

Pattern: the agent pauses its run loop, serialises the question into a protocol message, and resumes on receipt of the answer — rather than injecting a raw "please choose A or B" into the conversation.

### 3. Multi-tier reasoning model routing (2026.8.1-beta.3)

OpenClaw introduces Sol/Terra/Luna/Ultra tiers for GPT-5.6 and maps each to a reasoning-budget ceiling. The per-agent resolver picks the cheapest tier that meets the task's declared complexity. The LLM router wraps provider selection with a `reasoning_tier` param that overrides the model-string shorthand.

Pattern: reasoning budget as a first-class routing dimension alongside provider and model name.

### 4. Gateway lifecycle supervision (2026.8.1-beta.3)

An external supervisor process monitors the gateway process and hands off active sessions across verified restarts. The handoff protocol: gateway signals readiness → supervisor marks old instance draining → new instance claims ingress → drain completes. No session drops even on cold restarts.

### 5. Durable channel delivery / dead-letter recovery (2026.7.2-beta.7)

Messages survive gateway restarts via a shared ingress drain. Each channel plugin writes to a durable queue; the ingress monitor replays unacknowledged messages on recovery. Applicable to Telegram, Slack, Signal, IRC, and others.

Pattern: separate the channel ingest step (write-to-durable-queue) from the dispatch step (deliver-to-runtime), so a restart loses nothing.

---

## What we can use in Lexicon

Ranked by value / effort. Each file path was verified to exist.

### Tier 1 — Spike now

**A. Multi-tier reasoning routing** · Value: HIGH · Effort: LOW

`src/engine/llm/router.py` — `PersonaLLMRouter.resolve()` already resolves provider + model per persona. Adding a `reasoning_tier: str | None` parameter and threading it into the Anthropic provider call (`thinking.budget_tokens`) is a small, isolated change with immediate payoff: cheaper calls for quick tools, full reasoning for deep tasks.

`src/engine/llm/provider.py` — base `LLMProvider` abstract class needs `reasoning_tier` in its call signature.

`src/engine/llm/claude_provider.py` — concrete implementation where `thinking.budget_tokens` would be set per tier.

**B. Structured question approvals** · Value: HIGH · Effort: MEDIUM

`src/gateway/protocol.py` — already defines typed message classes. Add a `QuestionCard` message (question text + typed options list) and a `QuestionAnswer` response type.

`src/engine/orchestrator.py` — the sub-agent dispatch loop can be extended to check for a `QuestionCard` return and pause/resume around it, similar to how it already handles `ONESHOT` vs long-running modes.

`src/gateway/router.py` — route `QuestionAnswer` messages back to the waiting sub-agent session.

### Tier 2 — Plan in the next sprint

**C. Session branching** · Value: HIGH · Effort: HIGH

`src/engine/memory/transcript_index.py` — already indexes the transcript. Extend with a branch pointer per message: `parent_id`, `branch_id`, `is_active_branch`. The manager rehydrates only the active branch.

`src/engine/memory/manager.py` — `MemoryManager` would expose `fork_at(message_id)` and `switch_branch(branch_id)`, which snap the short-term and working memory to the chosen checkpoint.

`src/engine/runtime.py` — `AgentRuntime` needs to be branch-aware on init, loading from the correct checkpoint rather than always appending to the tip.

**D. Durable ingress queue** · Value: MEDIUM · Effort: HIGH

`src/engine/queue.py` — `CommandQueue` is currently in-memory. Swap the backing store to SQLite (already a project dependency per the beta's backup/restore additions), persisting each enqueued command. On startup, replay un-drained commands before accepting new ones.

`src/cron/store.py` — existing cron store uses SQLite; the queue can reuse its connection pool pattern.

### Tier 3 — Monitor / defer

**E. Gateway lifecycle supervision** · Value: MEDIUM · Effort: MEDIUM

`src/gateway/server.py` — the `lifespan()` context manager is the right place to emit a readiness signal. A companion supervisor script (outside src/) would monitor the process and orchestrate drain/restart. Low urgency unless Lexicon sees production availability issues.

**F. Secret egress host binding** · Value: MEDIUM · Effort: LOW

`src/vault/` — verify that outbound credential-bearing requests are bound to an allowlisted host set before being fired. More a security audit than a new pattern.

---

## My picks for what to spike next

1. **Spike A (reasoning tiers)** first — isolated to three files in `src/engine/llm/`, zero protocol changes, directly improves cost/quality tradeoff on every agent call. Could land in a single PR.

2. **Spike B (question approvals)** second — the protocol layer (`src/gateway/protocol.py`) and orchestrator pause/resume are the interesting engineering; the UI side (rendering option cards) can follow. This eliminates the biggest UX friction in multi-step agent flows.

3. **Plan C (session branching)** for the next sprint — `transcript_index.py` gives a solid foundation; the branch data model should be designed carefully before coding.
