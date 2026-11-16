# OpenClaw Watch — 2026-11-16

**Versions covered:** 2026.5.27 → 2026.11.4 (stable), 2026.5.28-beta.2 → 2026.11.5-beta.4  
**Last checked:** 2026-09-23  
**Sources:** github.com/openclaw/openclaw/releases, openclaw docs release index  

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.8.1 | Aug 30 | Stable | OpenClaw 2.0 — rebuilt agent runtime, stronger memory + session continuity |
| 2026.9.x | Sep 2026 | Stable | OpenAI Agents API, teams of specialist agents, hot-reload plugins, background tasks |
| 2026.9.37 | Late Sep | Extended-stable | Gateway maintenance: SQLite replay safety, MCP loopback recovery, plugin admission speed |
| 2026.10.x | Oct 2026 | Stable | Skill Workshop 2.0, MCP Apps, installed-skill discovery, security hardening, full backup/recovery |
| 2026.11.1–.4 | Nov 1–16 | Stable | Reliability pass: gateway restart safety, long-conversation fixes, privacy hardening |
| 2026.11.5-beta.1–.4 | Nov 2026 | Pre-release | Deferred MCP tool exposure, memory pressure reduction, paged history, binary attachment filtering |

---

## What's notable

### 1. Hot-reload skills/tools without restart (v2026.9.x)
Plugins and skills can now be installed and activated without restarting the agent runtime. The pattern uses a watcher on the skill registry that diffs registered vs. discovered skills and applies additions/removals in-process. Pure dep-bumps are ignored; only new capability surfaces trigger a hot-swap.

### 2. Multi-agent specialist teams (v2026.9.x)
OpenClaw added a first-class concept of "agent teams" — a named set of specialist agents with scoped skills and tool access, coordinated by a lightweight orchestrator that routes tasks by declared capability. This is distinct from simple routing: each team member can spawn sub-tasks back into the queue.

### 3. Memory compaction under pressure (v2026.11.5-beta.3)
Large sessions now reduce memory pressure during indexing, trimming, and compaction by streaming transcript chunks rather than loading them in full. The compactor defers non-critical index writes to a background worker and prioritises keeping the working context window intact.

### 4. Deferred MCP tool exposure (v2026.11.5-beta.3)
Tools from MCP servers are no longer pre-loaded into the prompt at session start. Instead, the runtime maintains a "deferred tools" manifest and resolves schemas on first reference. This shrinks the context overhead on sessions with many tool providers.

### 5. Binary attachment filtering (v2026.11.5-beta.4)
Binary attachments (images, files) are now explicitly stripped from the model prompt construction path. The pattern intercepts the message before it reaches the LLM provider and replaces blob content with a typed stub, keeping the token count predictable and preventing accidental context bloat from large attached files.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified to exist under `src/`.

| # | Pattern | Value | Effort | Lexicon target |
|---|---|---|---|---|
| 1 | **Memory compaction under pressure** | High | Medium | `src/engine/memory/manager.py`, `src/engine/context/compactor.py`, `src/engine/context/pruner.py` |
| 2 | **Hot-reload skills/tools** | High | Medium | `src/engine/skills.py`, `src/engine/hooks/loader.py`, `src/engine/tools/registry.py` |
| 3 | **Deferred tool exposure** | Medium | Low | `src/engine/tools/registry.py`, `src/engine/runtime.py` |
| 4 | **Binary attachment filtering** | Medium | Low | `src/engine/context/pruner.py`, `src/engine/llm/provider.py` |
| 5 | **Multi-agent specialist teams** | High | High | `src/engine/orchestrator.py`, `src/cron/scheduler.py` |

### Notes per item

**1. Memory compaction** — `src/engine/context/compactor.py` already has a compactor stub; the OpenClaw pattern of streaming transcript chunks rather than a full load could directly replace the in-memory approach in `src/engine/memory/manager.py`. Spike: instrument `manager.py` peak RSS on a large session, then switch transcript reads to chunked iteration in `compactor.py`.

**2. Hot-reload skills** — `src/engine/hooks/loader.py` loads hooks at startup; `src/engine/skills.py` registers skills similarly. Adding a file-watcher (e.g. `watchdog`) plus a diff-and-apply step in `loader.py` would enable live skill additions without restarting the gateway. Low disruption since the hook registry already isolates registration from invocation.

**3. Deferred tool exposure** — `src/engine/tools/registry.py` currently registers all tools up front. Converting this to a lazy-resolution pattern (register name+schema-fetch-callback, resolve only on first call) would shrink prompt size for sessions that use few tools. Low-effort: the registry interface is already a single call site.

**4. Binary attachment filtering** — `src/engine/context/pruner.py` prunes by token count but doesn't type-check message content. Adding a pre-pass that replaces binary blobs with typed stubs before the pruner runs would prevent large attachments from consuming token budget and reaching the LLM provider.

**5. Multi-agent teams** — `src/engine/orchestrator.py` has the routing skeleton. The team concept (scoped skill sets per agent, task hand-off back to queue) would require `src/cron/scheduler.py` to support per-agent task queues. Worth planning but high effort; park until 1–4 are done.

---

## My picks for what to spike next

**Primary:** Memory compaction (#1). Lexicon already has `compactor.py` and `pruner.py`; the pattern is a direct upgrade to an existing module with measurable impact on large-session performance. No new dependencies needed.

**Secondary:** Deferred tool exposure (#3). One-day spike in `src/engine/tools/registry.py`. Immediately shrinks context overhead for multi-tool sessions and unblocks adding more MCP providers without paying the prompt-size cost up front.
