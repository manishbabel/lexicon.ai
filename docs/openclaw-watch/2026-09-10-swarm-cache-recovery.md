# OpenClaw Watch — 2026-09-10

**Baseline:** 2026.5.27 stable / 2026.5.28-beta.2  
**New stable:** 2026.9.3 (Sep 8) — previous seen: 2026.5.27  
**New beta:** none newer than baseline  
**Sources checked:** github.com/openclaw/openclaw/releases (primary); releasebot.io and docs.openclaw.ai blocked by network egress policy

---

## What Shipped

### 2026.9.3 — Sep 8, 2026 (latest stable)
- Isolated candidate state during runtime updates (safer hot-reload)
- Warm prompt-cache preservation across restarts
- Persistent skill collections (skill state survives process restart)
- Swarm orchestration GA + cross-agent session access
- Live browser repainting, searchable meeting library, Team Reports integration
- **Breaking:** Node ≥24.16.0 or ≥26.1.0 required; `infra-runtime` utilities relocated to `execPolicy`; search result callbacks read from `details.content`

### 2026.9.2 — Sep 5, 2026
- Background transcript processing (compaction off the hot path)
- GPT-6 Astra model support with reasoning controls and async tools
- Gateway restart reply recovery — preserves continuation instructions across process restarts
- Git backup improvements: special-character handling + corrupt archive detection
- Swarm orchestration enabled by default, Discord meeting-notes capture

### 2026.6.35 — Sep 10, 2026 (LTS / Extended Stable)
- Bounded provider responses: hard cap on response size prevents memory exhaustion
- Resilient delivery with proper cancellation handling
- Stronger plugin error recovery
- Safer tool/workspace input validation

### 2026.8.x (two point releases)
- Maintenance / stability — no new patterns

---

## What's Notable

### 1. Bounded provider response limits (2026.6.35 LTS)
OpenClaw's LTS line added a hard ceiling on LLM response size before buffering. Responses that exceed the cap are streamed into a bounded sink and the remainder is cancelled cleanly. This prevents a runaway provider from exhausting heap under load — a class of failure that's hard to reproduce in tests.

### 2. Warm prompt-cache preservation on restart (2026.9.3)
Instead of flushing and reloading context on every process restart, OpenClaw now serialises the warm-cache metadata alongside conversation state and replays it into the provider client on the next boot. Round-trip latency for the first post-restart turn drops significantly.

### 3. Gateway restart reply recovery (2026.9.2)
In-flight replies now survive Gateway process restarts. On shutdown, the Gateway serialises each active session's continuation instructions; on boot it re-enqueues them for delivery. No reply drops on rolling deploys.

### 4. Background transcript processing (2026.9.2)
Context compaction is now scheduled as a background job decoupled from the request/response cycle. The hot path returns immediately; compaction runs asynchronously and writes updated context back into the session store.

### 5. Persistent skill state (2026.9.3)
Skill collections are now serialised to durable storage, so loaded skills and their in-memory registrations survive process restarts without a cold re-load pass.

---

## What We Can Use in Lexicon

Ranked by value / effort. Every file path verified present in the repo.

| # | Pattern | Value | Effort | Lexicon target |
|---|---------|-------|--------|----------------|
| 1 | **Bounded provider responses** — cap response buffer in LLM layer to avoid OOM | High | Low | `src/engine/llm/provider.py` |
| 2 | **Gateway restart reply recovery** — serialise in-flight session state on shutdown, re-enqueue on boot | High | Medium | `src/gateway/session.py`, `src/gateway/server.py` |
| 3 | **Prompt cache preservation** — persist warm-cache metadata alongside session state for fast post-restart first-turn | High | Medium | `src/engine/llm/router.py`, `src/engine/llm/claude_provider.py` |
| 4 | **Background transcript compaction** — move context pruning/compaction off the hot path via internal queue | Medium | Medium | `src/engine/context/compactor.py`, `src/engine/context/pruner.py`, `src/engine/queue.py` |
| 5 | **Persistent skill state** — serialise skills registry to survive restarts without cold re-load | Medium | Medium | `src/engine/skills.py`, `src/engine/hooks/registry.py` |

---

## Picks for What to Spike Next

1. **Bounded provider responses** (`src/engine/llm/provider.py`): A one-function change — wrap the streaming sink with a byte counter and cancel when threshold exceeded. The LTS lineage means the pattern is well-battle-tested. Immediate defensive win.

2. **Gateway restart reply recovery** (`src/gateway/session.py` + `src/gateway/server.py`): Lexicon currently drops in-flight replies on any process restart (rolling deploy, crash). Serialising session continuation state is the highest user-visible win in this batch — no dropped replies on deploy.
