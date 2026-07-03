# OpenClaw Watch — 2026-07-03

**Stable**: 2026.6.11 (June 30, 2026)  
**Beta**: 2026.7.1-beta.1 (July 2, 2026)  
**Baseline**: 2026.5.27 stable / 2026.5.28-beta.2 beta

---

## What Shipped

### 2026.6.1 — Resilient Agent and Codex Runs (early June)
- Interrupted tool calls, stale session bindings, compaction handoffs, and auth-profile failovers now recover without stranding work
- Live session locks held during cleanup; interrupted CLI tool transcripts restored
- Agent identity preserved through compaction cycles
- Skill Workshop gains guarded approval flows, disabled-skill snapshots, versioned proposal metadata with rollback safeguards
- SQLITE_BUSY write conflicts serialized in memory layer

### 2026.6.8 — Rich Channel Rendering + Usage Footers (mid-June)
- Telegram renders structured text: tables, lists, expandable blockquotes, preserved line breaks
- `/usage` reply hooks get a native full footer renderer with credential-aware limits and fixed-decimal formatting
- Web search key-free providers (DuckDuckGo, Codex Hosted Search) stay explicit opt-ins; no silent fallback
- Oversized OpenAI embedding batches auto-split before timeout; QMD search available in transient mode
- Claude Haiku 4.5 catalog entry added

### 2026.6.11 — Reliability Sweep (June 30, 2026) — **new stable**
- Fallback models activate automatically when primary providers hit usage limits or timeout
- Compaction no longer loses conversation context on user-initiated stop
- Saved summaries strip raw tokens, tool blocks, and stale markers from memory
- Per-DM model overrides for shared gateway users
- Security: trusted package paths reject lookalike sibling directories; DOMPurify GHSA-cmwh-pvxp-8882 patched
- Cloud model cron jobs recover from silent calls by default; scheduled runs reject disabled destinations
- Readiness checks unhealthy during gateway restarts to prevent traffic routing to updating nodes

### 2026.7.1-beta.1 — Capability Profiles + Event-Driven Cron (July 2, 2026) — **new beta**
- **Capability profiles**: per-conversation tool and access boundaries without weakening the default profile
- **`on-exit` cron schedule type**: agent fires when a monitored command or session exits
- External harness attachment via `openclaw attach` — resume and inspect running Gateway sessions
- GPT-5.6 and Nemotron Super support with 1M context window
- iMessage native poll creation and voting
- Built-in per-turn usage footers in chat display
- Cursor Agent autoreview engine integration
- Expanded diagnostics for auth profiles, workspaces, device pairing, systemd exhaustion

---

## What's Notable

### 1. Per-Conversation Capability Profiles
Conversations can now carry a scoped profile that restricts which tools and access paths are active — without touching the default profile used by other sessions. This is a clean runtime-level boundary rather than a blanket permission change. The implementation lives in the agent runtime and session layer, not the skill registry, which means profiles travel with the session context rather than being re-evaluated per-tool.

### 2. Event-Driven Cron (`on-exit` schedule type)
Cron is no longer purely time-based. The `on-exit` type fires an agent when a monitored process or session terminates. This enables pipelines where step N triggers step N+1 on completion — closer to a lightweight DAG than a traditional scheduler. Combined with the existing `openclaw attach` harness, this is a significant scheduling upgrade.

### 3. LLM Provider Fallback on Exhaustion/Timeout
The router now automatically activates a fallback model when the primary provider returns a usage-limit or timeout error. Previously this required manual intervention or a retry loop. The pattern: maintain an ordered fallback chain in the router config and let the runtime promote on failure, preserving speed settings through the transition.

### 4. Tool-Call Interruption Recovery
Agent identity and transcript state survive compaction cycles and restart. The key invariant: session locks are held through cleanup, not released early. Interrupted tool transcripts are restored rather than dropped. This closes a class of "lost work" bugs that appear when the context window is compacted mid-run.

### 5. Memory Hygiene: Stale-Marker Exclusion
Saved summaries now strip raw tokens, tool call blocks, and stale markers before writing to memory. This keeps the memory layer clean without a separate sweep pass — the exclusion happens at write time. Pairs naturally with serialized writes to avoid SQLITE_BUSY under concurrent agents.

---

## What We Can Use in Lexicon

Ranked by value/effort. All file paths verified against the current `src/` tree.

| # | Pattern | Value | Effort | Lexicon files |
|---|---------|-------|--------|---------------|
| 1 | **Per-conversation capability profiles** — scope which skills/tools are active per session context without changing the default | High | Medium | `src/engine/skills.py`, `src/gateway/session.py` |
| 2 | **Event-driven cron (`on-exit`)** — fire a cron job when a monitored session or subprocess exits, enabling lightweight pipelines | High | Low-Medium | `src/cron/scheduler.py`, `src/cron/store.py` |
| 3 | **LLM provider fallback on exhaustion/timeout** — router promotes to next provider in chain on usage-limit or timeout error | High | Low | `src/engine/llm/router.py` |
| 4 | **Tool-call interruption recovery** — hold session lock through compaction; restore interrupted tool transcripts on resume | Medium | Medium | `src/engine/runner.py`, `src/engine/context/compactor.py` |
| 5 | **Memory write hygiene** — strip raw tokens, tool blocks, stale markers at write time rather than sweep | Low-Medium | Low | `src/engine/memory/manager.py` |

---

## My Picks for What to Spike Next

**Spike 1 (highest priority): LLM provider fallback on exhaustion/timeout**  
`src/engine/llm/router.py` already has multi-provider routing logic. Adding an ordered fallback chain that promotes on `RateLimitError` / `TimeoutError` is a low-effort, high-reliability win. The pattern from 2026.6.11 is clear: maintain `primary → fallback[]`, promote on failure, preserve `fast_mode` setting through the transition.

**Spike 2: Per-conversation capability profiles**  
`src/engine/skills.py` currently loads skills globally. Adding a `CapabilityProfile` that gates `skills.py:get_available_tools()` by session context would let Lexicon restrict what tools fire per conversation — useful for untrusted channels or focused task sessions. `src/gateway/session.py` is where the profile would be attached at session creation.

**Spike 3: Event-driven cron**  
`src/cron/scheduler.py` + `src/cron/store.py` already handle time-based scheduling. An `on-exit` trigger type would need a subprocess completion hook wired into the scheduler's event loop — low surface area change with a meaningful workflow unlock.
