# OpenClaw Watch — 2026-09-11

**Versions covered:** 2026.8.1 (OpenClaw 2.0) through 2026.9.4  
**Baseline:** 2026.5.27 stable / 2026.5.28-beta.2 beta  
**Period:** late May → September 11, 2026

---

## What Shipped

| Release | Date | Headline |
|---------|------|----------|
| 2026.8.1 | ~Aug 2026 | **OpenClaw 2.0** — rebuilt session architecture, Grounded Dreaming memory, credential egress control, conversation-bound automations, Slack at Scale |
| 2026.8.2 | ~Aug 2026 | Extended stable maintenance patch on 2.0 |
| 2026.6.35 | Sep 10, 2026 | Final June LTS — provider response bounding, oversized-input rejection, delivery retry safety |
| 2026.9.1 | ~Sep 2026 | Foundation / dependency groundwork for 2026.9 line |
| 2026.9.2 | ~Sep 2026 | Prompt cache performance, cold session update optimization |
| 2026.9.3 | Sep 8, 2026 | Node 24 minimum, SDK exec/comparator refactor, Skill Workshop persistent collection, warm cache preservation, public transcript sharing |
| 2026.9.4 | Sep 11, 2026 | Plugin workspace unified in Control UI, cloud session prepared workers, read-only config mode (`OPENCLAW_CONFIG_READONLY=1`), voice subagent completion recovery |

Full release notes: https://github.com/openclaw/openclaw/releases

---

## What's Notable (Architecture / Runtime Patterns)

### 1. Grounded Dreaming — provenance-qualified memory consolidation (2026.8.1)
Background process promotes conversation content into long-term memory only after provenance qualification (source agent, session, timestamp chain). Writes to a Dream Diary log before admission. Operators can exclude specific source sessions and remove identifiable derived memory without touching raw transcripts. This separates *admission policy* from *storage* cleanly.

### 2. Live Model Discovery — dynamic provider enumeration (2026.8.1)
Agents no longer rely on a static built-in model snapshot. At startup, and on-demand, the runtime queries each configured provider's discovery endpoint and merges results into the model registry. Per-agent credentials scope discovery, so an agent only sees models its credentials can reach. Optional provider packages (BytePlus, Mistral, NovitaAI, etc.) install lazily rather than bundling.

### 3. Conversation-Bound Automations — cron anchored to conversation context (2026.8.1)
Scheduled jobs created within a session default their delivery target to the originating conversation rather than a global alert channel. `/loop` is owner-only and accepts either a fixed interval or a self-paced interval where the agent decides delay. Ambient heartbeat alerts route to resolvable owner DMs, silently skipping unroutable polls.

### 4. Credential Egress Control — proxy-scoped credential lifecycle (2026.8.1)
Agent credential requests surface through masked prompts; values never appear in chat context or model input. A proxy connection holding credentials closes when the owning run ends — replacement runs cannot revive sealed subprocess values. Users grant per-operation automation approval, inspect, and revoke later; fresh approval is required when job parameters change.

### 5. Warm Prompt Cache Preservation (2026.9.3)
Cold session updates previously invalidated in-flight prompt caches. OpenClaw now serializes the cache state before tearing down the session and restores it on the first incoming request of the replacement session, avoiding full re-population on startup. Related: memory searches during cold updates are deferred rather than aborted.

---

## What We Can Use in Lexicon

Ranked by **value / effort**. Every file path verified to exist in the repo.

### ★★★ High value / Medium effort

**A. Grounded Dreaming → `src/engine/memory/manager.py` + `src/engine/memory/episodic.py`**  
Lexicon has episodic memory and a manager but no background consolidation pass. Add an async consolidation task in `manager.py` that batches recent `episodic.py` entries, attaches a provenance envelope `{agent_id, session_id, ts}`, and admits them to long-term store only after a configurable hold period. Dream Diary can be a simple append-only log in `src/engine/memory/`. Low blast radius — existing retrieval path untouched.  
*Effort: ~1 sprint. Value: prevents memory pollution from unreliable sources.*

**B. Live Model Discovery → `src/engine/llm/router.py` + `src/engine/llm/provider.py`**  
`router.py` currently routes against a static provider registry. Add a `refresh_models()` async method on each provider (`claude_provider.py`, `openai_provider.py`, `litellm_provider.py`) that hits the provider's models endpoint and merges into the router's model map at startup and on SIGHUP. The `provider.py` base class should define the interface. Unblocks adding new models without a deploy.  
*Effort: ~3 days. Value: removes redeploy-to-add-model friction.*

### ★★ Medium value / Low effort

**C. Credential Egress Control → `src/gateway/session.py` + `src/gateway/server.py`**  
Lexicon passes tool credentials through the agent context dict. Add a sealed-credential wrapper: credentials are fetched at job start, stored in a session-scoped dict keyed by op-hash, and deleted when the session closes. `server.py` can enforce that the credential dict is not accessible after session teardown. Masked prompt surfacing is a UI concern but the backend sealing is a one-file change.  
*Effort: ~1–2 days. Value: hardens against credential leakage across tool calls.*

**D. Conversation-Bound Automations → `src/cron/scheduler.py` + `src/cron/store.py`**  
`CronJob` in `store.py` has a `target` field (`isolated`/`main`/`system`). Add a `conversation_id` field and a default-to-originating-conversation policy in `scheduler.py`'s `_execute_job`. When `conversation_id` is set, route the job's output to that conversation's queue instead of the global command queue.  
*Effort: ~1 day. Value: makes scheduled digests feel native to the conversation that spawned them.*

### ★ Lower value / Higher effort

**E. Warm Prompt Cache Preservation → `src/engine/context/compactor.py`**  
`compactor.py` manages context compaction. Add a cache-state snapshot method that serializes the current provider cache key(s) before a planned session restart. On session reinit, pass the snapshot to the first LLM call as a cache-restore hint. Requires per-provider support (Anthropic prompt-caching API) but the compactor is the right place to coordinate it.  
*Effort: ~1 sprint + provider negotiation. Value: faster agent restarts, lower token cost on repeat tasks.*

---

## Spike Picks

1. **Spike A — Grounded Dreaming** in `src/engine/memory/manager.py`: highest signal-to-noise ratio, existing module surface is the right fit, and the pattern solves a real Lexicon problem (undifferentiated episodic writes).

2. **Spike B — Live Model Discovery** in `src/engine/llm/router.py`: three provider files already exist with a uniform interface; the delta is small and the operational win is large.

3. **Spike D — Conversation-Bound Automations** in `src/cron/scheduler.py`: one-field addition to `CronJob`, routing change in `_execute_job`. Delivers noticeably better UX for Lexicon's scheduled digests.
