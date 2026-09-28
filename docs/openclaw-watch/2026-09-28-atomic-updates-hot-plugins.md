# OpenClaw Watch Digest — 2026-09-28

## What Shipped

| Version | Date | Type | Scale |
|---------|------|------|-------|
| **2026.9.5** | Sep 19, 2026 | Stable | 64 direct commits, 503 contributors, 4 179 PRs |
| **2026.9.6** | Sep 23–24, 2026 | Stable (hotfix rebuild) | macOS launch crash — rebuilt + notarized at 09:52 UTC |
| **2026.8.1** | Aug 30, 2026 | Stable ("OpenClaw 2.0") | Major milestone; usability, redesigned UI, cloud sessions |
| **2026.8.1-beta.3** | Aug 2026 | Beta | Pre-release for the 2.0 line |

> **Context:** State.json was frozen at 2026.5.27 / 2026.5.28-beta.2. This digest covers the 2026.9.5 cycle as the substantive release; 2026.9.6 is a hotfix-only rebuild and is not pattern-worthy. 2026.8.1 ("2.0") is noted as background context.

### Headline changes in 2026.9.5
- **Atomic Updates**: runtime verifies next version integrity before committing the switch, with rollback on validation failure.
- **Hot plugin installation**: install a plugin without restarting the Gateway; runtime registers new routes/tools in-process.
- **Conversation archives**: persistent cross-session conversation retrieval with search.
- **Specialist agent team setup**: guided declarative config for spinning up a named team of sub-agents, each with its own skill/tool scope.
- **GPT Live integration**: real-time LLM audio in meetings and phone calls (collocated with agent runtime).
- **Browser-alongside-agent**: share a live browser page with the agent during a session.

---

## What's Notable (Patterns Worth Watching)

### 1. Atomic runtime handover
OpenClaw now validates the next agent-runtime build in a staging slot before swapping the active slot. If the staged version fails a self-check, it rolls back automatically. This prevents a bad deploy from killing in-flight tasks — a direct answer to the "lost task on restart" class of bugs.

### 2. Gateway-layer hot registration
Plugins register their routes/tools into the live Gateway without a process restart. The Gateway exposes a dynamic-registration API that plugins call at install time. This is distinct from file-watch hot-reload (reloading skill files): it covers arbitrary new HTTP routes and tool descriptors added at runtime.

### 3. Cross-session conversation archives
Conversations are persisted with a searchable index and surfaceable as a "past context" tool call. The agent can retrieve a prior conversation by semantic query, not just by session ID. This makes episodic recall first-class rather than a side-effect of memory compaction.

### 4. Declarative specialist-agent team manifest
A `team.yaml` (or equivalent) declares each sub-agent's name, skill set, tool allowlist, and routing conditions. The orchestrator bootstraps the full team from this manifest at startup. Previously, team composition was ad-hoc per `route_to_agent` call.

### 5. In-process LLM audio colocation
The LLM provider and the audio transcription pipeline share a single event loop, avoiding the inter-process overhead of a separate audio service. The provider emits partial transcript tokens directly into the agent's message stream.

---

## What We Can Use in Lexicon

Ranked by value/effort (High value first):

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---------|-------|--------|-----------------|
| 1 | **Cross-session conversation archives** | High | Medium | `src/engine/memory/episodic.py`, `src/engine/memory/transcript_index.py` |
| 2 | **Declarative specialist-agent team manifest** | High | Medium | `src/engine/orchestrator.py`, `src/shared/types.py` |
| 3 | **Gateway-layer hot registration** | Medium | Low | `src/gateway/server.py`, `src/gateway/router.py` |
| 4 | **Atomic runtime handover** | Medium | High | `src/engine/runtime.py`, `src/cron/scheduler.py` |
| 5 | **In-process LLM audio colocation** | Low–Medium | High | `src/audio/transcription.py`, `src/engine/llm/provider.py` |

### Notes per item

**1 — Cross-session conversation archives**
`src/engine/memory/transcript_index.py` already indexes transcripts, but retrieval is session-scoped. Extending it with a semantic cross-session query (`episodic.py`) and exposing that as a tool call is a contained change with high agent capability payoff.

**2 — Declarative team manifest**
`src/engine/orchestrator.py` builds sub-agents imperatively per `route_to_agent` call. A `team.yaml` loaded at startup (keyed to a workspace) would let operators configure multi-agent topologies without touching Python. `src/shared/types.py` would grow an `AgentTeamConfig` type.

**3 — Gateway-layer hot registration**
`src/gateway/server.py` currently requires a full restart to pick up new workspace routes. A lightweight dynamic-registration path (POST `/admin/register-workspace`) would let the gateway pick up new workspaces at runtime. Skills already hot-reload via `src/engine/skills.py`; this closes the gateway gap.

**4 — Atomic runtime handover**
`src/engine/runtime.py` and `src/cron/scheduler.py` have no staged-swap logic. Implementing this is high-effort (staging slot, self-check protocol, rollback) but valuable if Lexicon starts doing live deploys without service interruption.

**5 — In-process LLM audio colocation**
`src/audio/transcription.py` runs Deepgram asynchronously and `src/engine/llm/provider.py` is a separate abstraction. Merging their event loops could reduce latency for audio-heavy agents, but the gain is marginal until audio usage grows.

---

## My Picks for What to Spike Next

1. **Cross-session conversation archives** (`src/engine/memory/episodic.py` + `src/engine/memory/transcript_index.py`) — narrow, high-signal change. Add a `search_past_conversations(query: str)` tool and wire `episodic.py` to return across-session hits. Directly improves agent continuity for returning users.

2. **Declarative team manifest** (`src/engine/orchestrator.py`) — adds operational leverage for multi-agent setups without requiring code changes per team composition. Define the `AgentTeamConfig` schema in `src/shared/types.py` and load it in the orchestrator's init path.
