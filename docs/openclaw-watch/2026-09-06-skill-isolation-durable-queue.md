# OpenClaw Watch — 2026-09-06

Versions covered: **2026.8.1 → 2026.9.2** (last seen: 2026.5.27 stable / 2026.5.28-beta.2 beta)

---

## What shipped

| Version | Released | Headline |
|---------|----------|---------|
| 2026.8.1 | ~Aug 2026 | Gateway stability, session migration reliability, reply completion, voice fixes |
| 2026.8.2 | 2026-09-01 | Linux desktop companion, Home agent sidebar, **background session creation**, **reasoning excluded from voice output**, authenticated browser control |
| 2026.9.1 | 2026-09-03 | **Personal skill libraries on shared Gateways**, durable Codex approvals, approval notifications to channels, Gateway stability, config-preserving updates |
| 2026.9.2 | 2026-09-05 | Faster chat, **automatic upgrade rollback**, **reply recovery across restarts**, **hot-reload settings without Gateway restart**, GPT-6 Astra provider, plugin icon branding |

*Source: github.com/openclaw/openclaw/releases (fetched 2026-09-06). Individual tag pages returned 404; descriptions are from the releases index.*

---

## What's notable

### 1. Per-workspace skill libraries (2026.9.1)
OpenClaw now lets each workspace maintain its own skill folder scoped to that Gateway instance. Skills in the workspace-local library override bundled ones by name, without touching the global install. This is essentially a workspace-scoped tier inserted between the system library and user overrides — giving multi-persona deployments safe skill isolation.

### 2. Durable reply queue — recovery after restarts (2026.9.2)
In-flight agent replies now survive a process restart. OpenClaw serialises the queue lane state to disk on each dequeue and replays incomplete entries on startup. The pattern separates "accepted" from "delivered" acknowledgement so no response is silently dropped.

### 3. Gateway hot-reload config (2026.9.2)
Settings (API keys, model selection, tool permissions) reload via a SIGHUP or a REST `POST /settings/reload` without taking the WebSocket server down. The pattern involves version-stamped config objects passed by reference through the service graph rather than read at import time.

### 4. Background session creation (2026.8.2)
Sessions are now provisioned eagerly in the background the moment a workspace is activated, not lazily on first message. The session is attached to its queue lane before any client connects, so the first-message latency disappears and cold-start dropouts are eliminated.

### 5. Reasoning excluded from output streams (2026.8.2)
When a provider emits thinking/reasoning tokens (e.g. extended-thinking models), OpenClaw's provider layer now filters them before writing to output channels (voice, UI stream). The provider contract gains a `reasoning_only` event type that consumers opt into separately.

---

## What we can use in Lexicon

Ranked by **value × effort** (high value, low effort first):

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---------|-------|--------|-----------------|
| 1 | **Workspace-scoped skill tier** | High | Low | `src/engine/skills.py` — three-tier precedence already exists (Tier 1–3); add a Gateway-instance tier between Tier 2 and 3, keyed by active workspace name | `workspaces/` contains per-persona `skills/` dirs already structured for this |
| 2 | **Durable reply queue (restart recovery)** | High | Medium | `src/engine/queue.py` — lanes exist but are ephemeral; add checkpoint serialisation (e.g. SQLite or JSONL sidecar) and replay on startup |
| 3 | **Reasoning token filtering in provider contract** | Medium | Low | `src/engine/llm/provider.py` — `stream()` already yields `LLMEvent`; add `reasoning` event variant so consumers (voice, UI) can ignore it without parsing content heuristics |
| 4 | **Gateway hot-reload config** | Medium | Medium | `src/gateway/server.py` — currently builds services in `lifespan()`; extract mutable config into a shared `ConfigStore` ref and add a `POST /settings/reload` endpoint |
| 5 | **Background (eager) session creation** | Low | Low | `src/gateway/session.py` — `SessionManager` creates sessions on demand; pre-warm on workspace activation by calling `create_session()` from the router on connect |

---

## My picks for what to spike next

1. **Workspace-scoped skill tier** (item 1 above). The `skills.py` three-tier system is already the right shape — adding a fourth tier keyed by workspace name is a one-file change. The `workspaces/` directories already have `skills/` subdirectories, so no schema migration is needed. Highest leverage for multi-persona deployments.

2. **Reasoning token filtering** (item 3). One new `LLMEvent` variant and a two-line filter in each consumer. Low risk, cleans up a latent footgun where voice output could expose chain-of-thought.

3. **Durable reply queue** (item 2). Bigger, but the `CommandQueue` lanes in `src/engine/queue.py` are the right place. Even a simple JSONL checkpoint on `_dequeue` + replay loop in `start()` would cover the common crash-recovery case.
