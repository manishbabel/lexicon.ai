# OpenClaw Watch — 2026-09-08

**Versions covered:** 2026.8.1 · 2026.8.2 · 2026.9.1 · 2026.9.2
**Previous baseline:** stable 2026.5.27 · beta 2026.5.28-beta.2

---

## What shipped

| Version | Date | Headline |
|---|---|---|
| 2026.8.1 | Aug 2026 | Gateway stability fixes; Codex integration with improved state management; plugin initialization hardening |
| 2026.8.2 | Sep 1, 2026 | Home agent accessible via dedicated keyboard shortcut (dockable panel); Linux desktop app (AppImage + .deb); background session creation without page-switch; safer upgrade path |
| 2026.9.1 | Sep 3, 2026 | Personal skill libraries on shared gateways; Mermaid diagram rendering; streamlined quick-start; update mechanism preserves config across failures |
| 2026.9.2 | Sep 5, 2026 | GPT-6 Astra model support; faster chat via architectural changes; reply recovery after engine restart; enhanced backup data preservation |

---

## What's notable

### 1. Personal skill libraries on shared gateways (2026.9.1)
Skills are now namespaced per user/session rather than loaded as a single global set. Shared gateway instances can serve different skill libraries to different sessions simultaneously. This is a fundamental shift from global skill loading to per-session skill resolution.

### 2. GPT-6 Astra provider integration (2026.9.2)
OpenClaw extended its LLM provider abstraction to support GPT-6 Astra. The pattern is instructive: the provider interface stayed stable while a new driver was dropped in, confirming their provider abstraction is working as designed.

### 3. Reply recovery after engine restart (2026.9.2)
In-flight replies now survive engine restarts. This implies a durable intermediate state layer—likely checkpointing active reply state to persistent store before completing delivery, then replaying on startup.

### 4. Home agent concept (2026.8.2)
A named "home" agent is now a first-class concept: always accessible via a shortcut, rendered in a dockable panel. This separates the concept of a *default routing target* from the rest of the agent registry—useful in multi-agent systems where users need a stable entry point.

### 5. Background session creation (2026.8.2)
Sessions are initialized asynchronously, decoupling the session bootstrap cost from the user-facing request path. The page/channel doesn't block waiting for session state to be fully established.

---

## What we can use in Lexicon

Ranked by value/effort (↑ = higher value, → = lower effort):

| # | Pattern | Value | Effort | Lexicon files |
|---|---|---|---|---|
| 1 | Per-session skill scoping | ↑↑ | → | `src/engine/skills.py`, `src/gateway/session.py` |
| 2 | GPT-6 Astra provider | ↑↑ | → | `src/engine/llm/litellm_provider.py`, `src/engine/llm/router.py` |
| 3 | In-flight reply persistence | ↑ | →→ | `src/engine/queue.py`, `src/engine/memory/working.py` |
| 4 | Home/default agent routing | ↑ | → | `src/engine/registry.py`, `src/gateway/router.py` |
| 5 | Async session initialization | → | → | `src/gateway/session.py` |

### Detail

**1 — Per-session skill scoping** (`src/engine/skills.py`, `src/gateway/session.py`)
`skills.py` currently resolves skills against a global registry. Passing a `session_id` into skill resolution would let shared-gateway sessions carry distinct skill sets—critical for multi-agent or multi-user Lexicon deployments (e.g., the `ai-educator` vs `software-engineer` workspaces loading different tool subsets). Change is local to `skills.py` + `session.py`.

**2 — GPT-6 Astra via LiteLLM** (`src/engine/llm/litellm_provider.py`, `src/engine/llm/router.py`)
Lexicon already has `litellm_provider.py`. GPT-6 Astra is accessible via an OpenAI-compatible endpoint—adding it is likely a model-name mapping + router entry. Low risk, immediate capability uplift.

**3 — In-flight reply persistence** (`src/engine/queue.py`, `src/engine/memory/working.py`)
Lexicon's `queue.py` manages pending tasks; `memory/working.py` holds short-lived state. Checkpointing active reply state to `working.py` on each streaming chunk, then replaying on startup, would make the engine restartable without dropping user responses.

**4 — Home/default agent routing** (`src/engine/registry.py`, `src/gateway/router.py`)
Add a `home` designation to `registry.py` (a single flagged entry) and expose it as `/` or a named route in `gateway/router.py`. Gives Lexicon a stable entry point for routing new sessions before context is established.

**5 — Async session init** (`src/gateway/session.py`)
Session construction in `gateway/session.py` can be made async so the gateway returns a session handle immediately while bootstrap completes in the background. Reduces perceived latency on first message.

---

## My picks for what to spike next

1. **Per-session skill scoping** — highest leverage for multi-user deployments; `src/engine/skills.py` is the clean entry point. Low blast radius, measurable win for the workspace isolation story.
2. **GPT-6 Astra in LLM router** — `src/engine/llm/litellm_provider.py` already abstracts model routing; adding Astra is likely a one-line model mapping. Fast win before the next release cycle.
