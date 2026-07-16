# OpenClaw Watch — 2026-07-16: Gateway Recovery & Cloud Workers

## What shipped

| Version | Date | Type | Headlines |
|---------|------|------|-----------|
| 2026.7.1 | 2026-07-13 | **stable** | Gateway crash-loop circuit-breaker; multi-provider LLM expansion (GPT-5.6+); enhanced Telegram/Slack/Discord/Apple Messages channel integrations; guided provider setup UX |
| 2026.7.2-beta.1 | 2026-07-15 | beta | Cloud worker dispatch for remote sessions; native automation/mobile node support; safer per-channel error isolation (Telegram, Signal); gateway session recovery improvements; Linux deb/AppImage packaging |

Previous tracked versions: `2026.5.27` (stable), `2026.5.28-beta.2` (beta).

---

## What's notable

### 1. Gateway crash-loop circuit-breaker (stable 2026.7.1)
The gateway previously had no back-off strategy on repeated failures — a bad session or provider error would spin the gateway into an infinite restart loop. 2026.7.1 introduces structured recovery: exponential back-off, a restart-count ceiling, and a "poisoned session" quarantine that isolates the failing session rather than cycling the whole gateway. This is a classic circuit-breaker pattern applied at the process boundary.

### 2. Cloud worker dispatch for remote sessions (beta 2026.7.2-beta.1)
Agent tasks can now be routed to a cloud worker pool rather than running inline on the gateway host. The runtime distinguishes between "local" and "remote" execution contexts at task-dispatch time. This decouples session handling from compute-heavy agent execution — relevant for any Lexicon scenario where LLM calls or long-running tools slow down the gateway event loop.

### 3. Per-channel error isolation (beta 2026.7.2-beta.1)
Channel operations (send/receive) are now wrapped in per-channel error boundaries. A failure on one channel (e.g. Telegram rate-limit) no longer propagates to others. Each channel gets its own retry budget and failure state; the protocol layer surfaces a unified health status.

### 4. LLM router provider capability detection (stable 2026.7.1)
Adding GPT-5.6 + new providers exposed that the existing "route by name" approach was brittle. The router now probes providers for capability flags (streaming, tool-use, vision, context-length) at startup and uses those flags for routing decisions, not just model-name string matching. A provider that doesn't respond to the capability probe is put into a degraded-routing tier.

---

## What we can use in Lexicon

Ranked by value / effort. All paths verified against the live `src/` tree.

| # | Pattern | Value | Effort | Lexicon files |
|---|---------|-------|--------|---------------|
| 1 | **Gateway circuit-breaker / session quarantine** | High | Low | `src/gateway/server.py`, `src/gateway/session.py` |
| 2 | **Per-channel error isolation** | High | Low | `src/gateway/protocol.py`, `src/gateway/router.py` |
| 3 | **LLM router capability probing** | Medium | Low | `src/engine/llm/router.py`, `src/engine/llm/provider.py` |
| 4 | **Cloud worker dispatch (remote execution context)** | Medium | High | `src/engine/runtime.py`, `src/engine/runner.py`, `src/cron/scheduler.py` |

**#1 — Gateway circuit-breaker:** `src/gateway/server.py` restarts sessions but has no back-off or failure ceiling today. Adding a restart counter + exponential delay before re-accepting a session is a low-touch change with a direct operational payoff — prevents a single bad LLM call from spinning the whole gateway.

**#2 — Per-channel error isolation:** `src/gateway/protocol.py` handles message dispatch; `src/gateway/router.py` routes by channel type. Wrapping each channel's send/receive in an isolated try/except with per-channel retry state means a Slack API outage won't affect voice or other channels sharing the same event loop.

**#3 — LLM capability probing:** `src/engine/llm/router.py` routes by provider name. A startup probe that checks which providers actually support streaming and tool-use would make `src/engine/llm/provider.py`'s abstract interface mean something at runtime, not just in code. Low effort, improves reliability when providers are misconfigured.

**#4 — Cloud worker dispatch:** Worthwhile eventually — `src/engine/runtime.py` runs everything inline. But this is a large architecture change; defer until gateway stability (#1, #2) is solid.

---

## Spikes

**Spike now:** Gateway circuit-breaker in `src/gateway/server.py`.  
Add a `_restart_attempts` counter per session and a `_last_restart_at` timestamp. If `_restart_attempts > N` within a rolling window, quarantine the session (log + skip) rather than looping. This is a two-hour spike with immediate operational value.

**Next:** Per-channel error isolation in `src/gateway/protocol.py` — wrap channel dispatch in a per-channel `ChannelCircuit` dataclass tracking failure count and backoff expiry.
