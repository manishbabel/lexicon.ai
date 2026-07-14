# OpenClaw Watch — 2026-07-14

## What shipped

| Version | Released | Headline |
|---|---|---|
| **2026.6.10** | 2026-06-24 | Adaptive fast-mode for short conversational turns |
| **2026.6.11** | ~2026-07-01 | Gateway reliability hardening — stale queue expiry, history caps, provider prompt hygiene |
| **2026.7.1** | 2026-07-13 | Major: gateway crash-loop recovery, utility model routing, 3 063 contributions from 532 contributors |
| 2026.7.1-beta.6 | 2026-07-13 | Model additions (Claude Sonnet 5, Meta Muse Spark 1.1, Featherless) |

All three stable releases are new since our last baseline (2026.5.27 / 2026.5.28-beta.2).

---

## What's notable

### 1. Gateway crash-loop recovery (2026.7.1)
When the gateway crashes repeatedly at boot, OpenClaw now enters **control-plane-safe mode**: boot outcomes are persisted to disk, transports and LLM providers are held offline, and the control/admin surface stays alive so operators can inspect and repair. Fatal configuration errors emit `EX_CONFIG` so `systemd`/`launchd` stop restart-flapping. This breaks the "crash → immediate restart → crash again" loop without requiring an external watchdog.

### 2. Utility model routing for metadata tasks (2026.7.1)
Session titles are now generated via a configurable **utility model** (cheaper/faster) separate from the agent's primary model — configurable per-agent. The pattern: classify tasks as `metadata` vs `agent` and route to different model tiers at the router layer, not the call site.

### 3. Stale queued-node TTL expiry (2026.6.11)
Queued gateway work that has been waiting too long now **auto-expires** before it runs. Prevents stale cron- or integration-enqueued tasks from executing in a context that has moved on. `QueuedMessage.enqueued_at` is already stamped; the missing piece is an expiry check at drain-time.

### 4. Per-integration subagent session history cap (2026.6.11)
When an integration (plugin/webhook) requests subagent session history, each read is now **capped at a safe limit**, preventing a single misbehaving integration from loading unbounded history into the gateway and stalling other work.

### 5. Adaptive fast mode (2026.6.10)
OpenClaw can switch to a **fast-mode model** for short conversational turns, then return to the primary model for longer/tool-heavy runs with bounded fallback and delivery guarantees. This reduces latency and cost for simple acknowledgements without changing the configured default.

---

## What we can use in Lexicon

Ranked by value/effort. Every file path verified to exist in the repo.

### 1. Utility model routing — `src/engine/llm/router.py`
**Value: HIGH / Effort: LOW**

`PersonaLLMRouter.resolve()` already accepts `provider` and `model` overrides. Add a `task_class: Literal["agent", "metadata"] = "agent"` parameter and a per-persona `utility_model` config key. When `task_class="metadata"` resolve to the utility model instead. Callers that generate session/thread titles (once we add them), cron summaries, or topic tags get cheaper inference with no changes outside the router.

### 2. Stale queue TTL expiry — `src/engine/queue.py`
**Value: MEDIUM / Effort: LOW**

`QueuedMessage` already stamps `enqueued_at`. In the lane-drain loop (where messages are popped and handed to `handle_run`), add a TTL check: if `time.time() - msg.enqueued_at > MAX_QUEUE_AGE_S`, drop the message and emit a warning. Prevents cron jobs queued during a long outage from firing all at once on recovery. A sensible default: `MAX_QUEUE_AGE_S = 300` (5 min) for `cron` lane, unlimited for `main`.

### 3. Gateway boot-state persistence + safe mode — `src/gateway/server.py`
**Value: MEDIUM / Effort: MEDIUM**

The `lifespan()` function starts all services in sequence with no crash-tracking. Add a small boot-outcome file (e.g. `.gateway_boot_state`) written before and cleared after successful startup. On a second startup that finds an uncleared prior state, skip transport binding and LLM provider init, serve only a `/health` endpoint with `{"status": "safe-mode", "reason": "previous_crash"}`, and log clearly. This makes repeated-crash debugging much easier and stops the server from hammering the LLM provider during a bad-config loop.

### 4. Per-integration context read cap — `src/engine/context/pruner.py`
**Value: MEDIUM / Effort: LOW**

Add a `max_tokens_per_integration_read: int = 8192` ceiling in the pruner (or in `src/engine/memory/short_term.py`'s retrieval path). Any caller that pulls history for a plugin or cron invocation should go through a capped retrieval rather than the full `ShortTermMemory` store. Prevents a single large session from blocking the cron lane.

### 5. Adaptive fast mode — `src/engine/llm/router.py`
**Value: LOW-MEDIUM / Effort: MEDIUM**

Extend `PersonaLLMRouter` with a `fast_model` per-persona config key. Expose a `resolve_fast()` method that returns the fast-mode model for low-complexity turns. `AgentRunner` (`src/engine/runner.py`) would need a heuristic to detect "short conversational turn" — e.g. `len(content) < 200 and no tools invoked last turn`. Worth doing only after #1 and #2 land.

---

## My picks for what to spike next

1. **Utility model routing** (#1) — the router already has the right shape, this is a 30-line change with immediate payoff for anything that auto-generates titles or summaries.
2. **Stale queue TTL** (#2) — a one-function addition that closes a real reliability gap visible on every cron-during-downtime scenario.
3. **Boot-state safe mode** (#3) — more involved but the existing `lifespan()` has no crash hygiene at all; this is the one operators feel first.
