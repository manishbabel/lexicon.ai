# OpenClaw Watch — 2026-10-13: Stability & Security Sprint

**Period covered:** 2026-09-24 → 2026-10-13
**Previous state:** stable 2026.5.27 / beta 2026.5.28-beta.2 (baseline, never verified)
**New state:** stable 2026.10.2 / beta 2026.10.5-beta.2

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.10.2 | Oct 12 | Stable (Latest) | Update reliability, secret-redaction hardening, prompt-cache stability, cron fixes |
| 2026.10.1 | Oct 10 | Stable | In-place update path groundwork |
| 2026.9.9 | Oct 8 | Stable | 185 commits / 112 PRs (full notes at CHANGELOG/2026.9.9.md) |
| 2026.9.8 | Oct 3 | Stable | 58 commits / 43 PRs (full notes at CHANGELOG/2026.9.8.md) |
| 2026.10.5-beta.2 | Oct 12 | Beta (Latest) | Tool-approval hardening, subagent provenance, network-taint propagation, memory hot-reload |

> Note: Significant releases between 2026.5.27 and 2026.9.8 were not tracked (prior watch runs blocked by network policy). The patterns below are drawn from what is verifiable.

---

## What's notable (patterns worth porting)

### 1. Prompt-cache stability — byte-identical prefixes across replays
`2026.10.2` — Anthropic checkpoints, prompts, tool results, and inter-session provenance are now kept byte-identical across replays and restarts, so cached prefixes keep hitting. This is a deliberate serialisation discipline, not an accidental side-effect.

### 2. Tool argument immutability after inline approval
`2026.10.5-beta.2` — Hooks can no longer mutate tool arguments after a trusted inline approval has been recorded. Plugins that need to transform arguments must request approval for their *final* arguments. This closes a TOCTOU window between approval and execution.

### 3. Network-result taint propagation
`2026.10.5-beta.2` — Network results surfaced through Tool Search and Code Mode now taint the turn the same way direct network-tool calls do. Previously only direct calls were tainted; indirect paths were unprotected.

### 4. Subagent provenance envelope through replay
`2026.10.5-beta.2` — Inter-session messages preserve their safety envelope when replayed, so parent-sent instructions are not re-presented to a child agent as direct user instructions. This prevents prompt-privilege escalation across orchestration hops.

### 5. Embedding provider hot-reload without gateway restart
`2026.10.5-beta.2` — Correcting an embedding provider's endpoint or credential refreshes cached index managers in place. No restart needed. The pattern is: invalidate the manager cache on config write rather than on startup.

---

## What we can use in Lexicon

Ranked by value/effort. Each path verified to exist in `src/`.

| # | Pattern | Value | Effort | File(s) |
|---|---|---|---|---|
| 1 | **Prompt-cache stability** — normalize serialisation of tool results and inter-session context so cache prefixes stay byte-identical across restarts | High | Low | `src/engine/llm/claude_provider.py` |
| 2 | **Tool arg immutability post-approval** — freeze tool call arguments once an approval is recorded; hooks registered after that point cannot mutate them | High | Medium | `src/engine/hooks/registry.py`, `src/engine/hooks/builtin.py` |
| 3 | **Network-result taint** — mark turns that consumed any network tool result (including via indirect tool wrappers) so downstream steps can gate on taint | Medium | Medium | `src/engine/runtime.py`, `src/engine/tools/web_search.py`, `src/engine/tools/rss_fetch.py` |
| 4 | **Subagent provenance envelope** — when routing to a child agent, wrap the payload with an origin label so the child cannot treat parent instructions as first-party user input | Medium | Medium | `src/engine/orchestrator.py`, `src/engine/tools/route_to_agent.py` |
| 5 | **Embedding hot-reload** — invalidate cached index managers in `memory/manager.py` on provider-config write instead of only at startup | Medium | Low | `src/engine/memory/manager.py` |

---

## My picks for what to spike next

1. **Prompt-cache stability** (`src/engine/llm/claude_provider.py`) — highest ROI, lowest risk. Ensuring byte-identical serialisation of the messages array before every Anthropic call will immediately improve cache hit rate and reduce cost. A one-function audit of how tool results and system prompts are serialised is the full scope.

2. **Tool arg immutability** (`src/engine/hooks/registry.py`) — closes a real security gap. Lexicon's hook registry currently applies all registered hooks sequentially with no approval checkpoint. Adding a freeze after the first approval match is a self-contained change with clear test surfaces.

3. **Embedding hot-reload** (`src/engine/memory/manager.py`) — quality-of-life win. Operators currently need a full process restart to pick up a changed embedding endpoint. The OpenClaw pattern (invalidate on config write) maps directly to how Lexicon's `shared/config.py` propagates changes.
