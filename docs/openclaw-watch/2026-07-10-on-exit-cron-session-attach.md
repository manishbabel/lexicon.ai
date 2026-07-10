# OpenClaw Watch — 2026-07-10

Covering releases since baseline (2026.5.27 stable / 2026.5.28-beta.2).

---

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.6.11** | 2026-06-30 | Stable | Reliability pass: routing, memory cache, heartbeat privacy, scoped capability profiles |
| **2026.7.1-beta.1** | 2026-07-02 | Beta | `openclaw attach`, GPT-5.6, event-driven cron (`on-exit`), Telegram Codex pairing |
| **2026.7.1-beta.2** | 2026-07-05 | Beta | Same feature set as beta.1, transient failure recovery, iOS 26 redesign |

**2026.6.11 key changes (architectural):**
- Heartbeat checks now hide internal reasoning from channel surfaces (Telegram, WhatsApp) — only the intended reply is delivered; opt-in Thinking mode still works.
- Long-context, tool-heavy sessions keep prompt-cache reuse steady across repeated turns without dropping per-result size limits.
- Improved task delivery routing when sessions lack full conversation context.
- Capability profiles establish per-conversation tool and access boundaries without weakening the global default profile.

**2026.7.1-beta.1/2 key changes (architectural):**
- `openclaw attach` launches an external harness against an existing live Gateway session — enabling resume and inspection of in-flight agent runs.
- New `on-exit` cron schedule kind wakes an agent when a watched command exits; session-targeted runs can detach cleanly without waiting for the session.
- Scoped conversation capability profiles (landed in stable 2026.6.11, extended here with finer-grained tool boundaries per conversation turn).

*Skipped as noise:* GPT-5.6 model catalog entry (dep update only), Telegram/WhatsApp/iOS channel-specific UI, Swedish localization, QQBot slash-command visibility, Google Chat DM routing fix.

---

## What's Notable

### 1. `on-exit` event-driven cron
OpenClaw's cron scheduler now supports a new schedule kind that fires when a watched subprocess exits rather than on a wall-clock interval. Internally this turns a polling loop into a pure event subscription — the agent sleeps until a process signal arrives, then starts exactly like a user message would. This is a meaningfully different execution model from time-based schedules and enables zero-latency pipeline triggers.

### 2. `openclaw attach` — external harness to live Gateway sessions
A CLI/API command that attaches an external agent harness to an already-running Gateway session without tearing it down. The protocol lets the external harness steer, inspect, and resume the session. This is the first public pattern for multi-harness session handoff.

### 3. Scoped capability profiles per conversation
Rather than one global tool allowlist, OpenClaw now mints a profile per conversation at session open time. The profile can narrow (never expand) the default tool set for that conversation. Profiles are applied before the runtime sees any turn — so tool calls from an LLM that tries to exceed its profile are rejected at the boundary.

### 4. Heartbeat reasoning privacy
Cron-fired heartbeat runs using reasoning-capable models (o3, extended-thinking, etc.) now suppress the chain-of-thought from channel surfaces. Only the resolved reply is delivered. The pattern: the runtime detects when a turn originated from a scheduled heartbeat, wraps the reasoning in a delivery filter before handing off to the channel adapter.

### 5. Prompt-cache reuse under tool-heavy memory pressure
The context compaction layer now tracks cache-anchor positions across tool-result turns and adjusts pruning to avoid invalidating anchors. Large tool results are capped separately from context anchors so a single big result doesn't blow the cache for the whole session.

---

## What We Can Use in Lexicon

Ranked by value/effort (high value first, easiest effort first within tier).

### High value

**A. Heartbeat reasoning privacy** — Effort: Low  
`src/cron/scheduler.py`, `src/engine/runtime.py`  
When a turn is scheduled (heartbeat/cron), tag it so the runtime can strip chain-of-thought before forwarding to the gateway. The scheduler already fires turns; add a `is_scheduled=True` flag on the run context and a delivery filter in `runtime.py` that checks it before returning to the gateway session.

**B. Scoped capability profiles per session** — Effort: Medium  
`src/engine/runtime.py`, `src/engine/skills.py`, `src/gateway/session.py`  
At session open in `gateway/session.py`, read a profile spec (from workspace config or agent identity) and mint a `CapabilityProfile` that narrows the global tool registry. Pass it through the runtime so `skills.py` tool dispatch checks the profile rather than the flat global registry. The pattern maps cleanly onto Lexicon's existing registry in `src/engine/tools/registry.py`.

**C. `on-exit` cron schedule kind** — Effort: Medium  
`src/cron/scheduler.py`, `src/cron/store.py`  
Add an `on_exit` schedule type alongside the existing time-based ones in `scheduler.py`. The scheduler watches a subprocess PID or command; when it exits, enqueue the cron job exactly as if its time had come. Store the watched PID/command in `store.py` alongside the existing schedule record. Enables pipeline-chained agent runs without polling.

### Medium value

**D. Prompt-cache stability under tool pressure** — Effort: Medium  
`src/engine/context/compactor.py`, `src/engine/memory/manager.py`  
Track cache-anchor positions in `compactor.py`. When pruning, prefer evicting non-anchor turns before anchor turns. Cap tool-result token budget separately from the anchor budget. This is low-risk and targets long agentic sessions (paper-reader, meeting-digest) that already stress context.

**E. External harness session attachment** — Effort: High  
`src/gateway/server.py`, `src/gateway/session.py`, `src/gateway/protocol.py`  
Expose an attach endpoint on the Gateway that accepts a session ID and returns a live write handle. Useful for developer tooling (inspect a stuck agent run, hand off from a webhook to an interactive session). High effort because it requires protocol changes; worth spiking after B is done.

---

## Picks for Next Spike

1. **Heartbeat reasoning privacy (A)** — one-day change, removes a live UX issue where reasoning leaks into channel messages. Start in `src/cron/scheduler.py` by tagging scheduled turns, then add the filter in `src/engine/runtime.py`.
2. **Scoped capability profiles (B)** — one-sprint change, strong safety property; the workspace/agent identity files (`workspaces/*/AGENT.md`) already contain tool declarations that could seed the profile spec.
3. **`on-exit` cron (C)** — spike in `src/cron/scheduler.py` using a background thread watching `subprocess.Popen`; the store schema in `src/cron/store.py` would need one new column.
