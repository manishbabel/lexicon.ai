# OpenClaw Watch — 2026-09-19

**Digest period:** 2026-05-27 (baseline) → 2026-09-19 (today)
**Compiled from:** github.com/openclaw/openclaw/releases, web search corroboration

---

## What shipped

| Version | Date | Type | Headline |
|---------|------|------|----------|
| 2026.6.35 | 2026-09-10 | LTS | Final June Extended Stable — provider/channel boundary sandboxing |
| 2026.7.2-beta.6 | ~2026-07 | Beta | State safety & recovery; GPT-5.6 provider |
| **2026.8.1** | **2026-08-31** | **Stable** | **OpenClaw 2.0 — largest release in project history (16,000 PRs, 933 contributors)** |
| 2026.9.4 | 2026-09-11 | Stable | Stability pass; signed npm publication |
| 2026.9.5 | 2026-09-19 | Stable | Latest — maintenance, no new architectural surface |

**Current stable:** 2026.9.5 (up from baseline 2026.5.27)
**Current beta:** 2026.7.2-beta.6 (up from baseline 2026.5.28-beta.2)

The headline release is **OpenClaw 2.0 (v2026.8.1)**. The 2026.9.x builds are stability-only. The 2026.6.35 LTS closes a security gap in provider/channel egress that is worth a standalone port.

---

## What's notable (5 patterns)

### 1. Background memory consolidation ("Grounded dreaming")
Model-backed background consolidation is now on by default. A scheduled task runs a model call to distil recent episodic events into durable compressed summaries ("Dream Diary"); the derived records carry provenance back to source transcripts, and users can inspect which sessions contributed and delete identifiable derived data without touching the originals. This turns memory into an append-only provenance graph rather than a flat store.

### 2. Masked credential requests — credentials never enter model context
When an agent needs a secret (API key, token, password), it calls a new primitive that surfaces a masked input field to the user *outside* the model context; the resolved value is injected directly into the outbound request, never appearing in the conversation or prompt. A 1Password broker integration extends this to service-account–resolved SecretRefs. A complementary "protected credential egress" rule tears down all proxy and upstream connections the moment their owning run ends.

### 3. Conversation-scoped automation binding
New agent-turn automations (cron triggers, loop callbacks) now default to the conversation context in which they were created, not a global registry. The owner can grant an automation permission for exactly one operation, inspect what was granted, and revoke it. This prevents scheduled tasks from accumulating ambient access across conversations over time.

### 4. Live model discovery (provider catalog at runtime)
Instead of a static catalog baked into source, providers are queried at startup for their currently available model list. The result is cached and refreshed on reconnect. This means new model IDs (e.g. new Claude or Mistral versions) are available without a Lexicon code change.

### 5. Provider/channel response-body sandboxing (from 2026.6.35 LTS)
Bundled providers and channel adapters now treat every response body as untrusted before surfacing it to the agent runtime — binding, sanitising, and schema-validating at the boundary. This closes the class of prompt-injection attacks that arrive via tool results or channel messages rather than direct user input.

---

## What we can use in Lexicon

Ranked by **value / effort** (H = high, M = medium, L = low).

| # | Pattern | Value | Effort | Lexicon target files |
|---|---------|-------|--------|----------------------|
| 1 | **Masked credential requests** | H | L | `src/shared/config.py`, `src/engine/llm/provider.py` |
| 2 | **Conversation-scoped cron binding** | H | L | `src/cron/scheduler.py`, `src/cron/store.py` |
| 3 | **Provider/channel response sandboxing** | H | M | `src/engine/llm/provider.py`, `src/gateway/router.py` |
| 4 | **Live model discovery** | M | L | `src/engine/llm/router.py` |
| 5 | **Background memory consolidation** | H | H | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py` |

### Detail

**1 — Masked credential requests** (`src/shared/config.py` L140–, `src/engine/llm/provider.py`)
Pattern: add a `request_secret(label)` helper in `shared/config.py` that writes the masked prompt to the UI channel and reads the response through a side-channel (not the model turn). `llm/provider.py` calls it when constructing headers for providers that require API keys not already in config. The key never appears in any transcript or prompt. Protected egress (tear down connections on run-end) slots into `src/gateway/session.py` cleanup.

**2 — Conversation-scoped cron binding** (`src/cron/scheduler.py`, `src/cron/store.py`)
Pattern: add `conversation_id` as a first-class field in the cron job schema (`store.py`). `scheduler.py` filters visible jobs by the active session's conversation ID. Automations created outside a conversation context are explicitly global-scoped (opt-in, not default). This is a one-field schema change + filter clause and is the lowest-effort win here.

**3 — Provider/channel response sandboxing** (`src/engine/llm/provider.py`, `src/gateway/router.py`)
Pattern: wrap all LLM/tool response bodies in a validation step before they touch the runtime — check for unexpected keys, enforce max size, strip prompt-injection markers. `gateway/router.py` does the same for inbound channel messages. This narrows the injection surface significantly without changing the public API.

**4 — Live model discovery** (`src/engine/llm/router.py`)
Pattern: each provider class gains a `list_models() -> list[str]` method; `router.py` calls it at startup and exposes a `GET /models` endpoint. Currently the router routes by a static config; replacing the static list with a cached live query is an incremental change.

**5 — Background memory consolidation** (`src/engine/memory/manager.py`, `src/engine/memory/episodic.py`)
Pattern: `memory/manager.py` grows a `consolidate()` method that reads recent `episodic.py` entries, runs a model call to produce a compressed summary, writes it back to episodic storage with a `derived_from` provenance list, and then schedules itself (via `src/cron/scheduler.py`) at a configurable interval. Higher effort because it requires a new LLM call inside the memory layer and a provenance schema, but the long-term quality gain is large.

---

## My picks for spikes next

1. **Conversation-scoped cron binding** (#2) — smallest scope, closes a real behaviour gap (cron jobs currently accumulate globally), ships in a day.
2. **Masked credential requests** (#1) — closes a security gap; credentials in transcripts are a liability. The side-channel plumbing is the only tricky part.
3. **Live model discovery** (#4) — removes a recurring manual update burden (adding new Claude/Mistral IDs to a static list) with a small provider-interface change.

Background memory consolidation (#5) is the highest long-term leverage but deserves its own spike planning session before starting.
