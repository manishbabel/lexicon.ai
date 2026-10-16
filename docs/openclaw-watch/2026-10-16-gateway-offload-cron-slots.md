# OpenClaw Watch — 2026-10-16: Gateway offload, cron slots, tool descriptor caching

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.9.33 | Sep 2026 | Extended-stable (LTS) | Gateway restart resilience; cron write-lock fixes; streaming re-parse optimization; provider deadlines |
| 2026.10.1 | Oct 2026 | Stable | Large release (3,055 commits, 402 contributors); Android build skipped |
| 2026.10.2 | Oct 2026 | Stable | No detailed notes available |
| 2026.10.3 | Oct 2026 | Stable | 90 commits, 79 PRs; gateway and runtime fixes |
| 2026.10.4 | 2026-10-16 | **Stable / Latest** | Gateway stability: no self-restart on sleep/clock changes; stalled workers no longer hang shutdown; `/compact` settles active run before compacting |
| 2026.10.10-beta.1 | 2026-10-15 | Beta | Gateway main-thread SQLite offload; experimental PostgreSQL for Workboard; tool descriptor caching; cron slot persistence; cloud session management |

Previous state: stable `2026.5.27`, beta `2026.5.28-beta.2` (last checked 2026-09-23).

---

## What's notable

### 1. Gateway main-thread SQLite offloading (2026.10.10-beta.1)
The Gateway now moves cold-session reads, memory SQL, and Workboard queries off the main thread during chat turns, session list renders, startup, and idle. An experimental PostgreSQL engine is also available as a Workboard store backend with migration tooling. This is the clearest signal that synchronous DB access in the request path is a known bottleneck at scale.

### 2. Cron slot state persistence (2026.9.33 + 2026.10.10-beta.1)
Two complementary fixes: (a) cron no longer holds the state writer while waiting on host admission, and (b) completed slots are not replayed and slots cancelled at Gateway stop are advanced past on the next run. Together these solve the "phantom replay" and "write starvation" failure modes for scheduled jobs.

### 3. Tool descriptor caching (2026.10.10-beta.1)
Tool descriptors and dynamic schemas are now reused between turns within a session, and session tools are initialized once rather than on every turn. This cuts per-turn overhead proportionally to the tool count.

### 4. Streaming re-parse optimization (2026.9.33)
Long streamed replies that start with a reply tag no longer trigger a full re-parse of the accumulated reply on every streaming delta. The fix replaces O(n) re-parsing with incremental state tracking.

### 5. Provider response-header deadlines (2026.9.33)
Local (self-hosted) LLM providers now have a response-header deadline, so a provider that accepts a connection but never sends a response header no longer stalls a worker indefinitely.

---

## What we can use in Lexicon

Ranked by value/effort (H = High, M = Medium, L = Low):

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---|---|---|---|
| 1 | **Tool descriptor caching** — build tool schema once per session, not per turn | H | L | `src/engine/tools/registry.py` |
| 2 | **Streaming re-parse fix** — incremental state tracking instead of full re-parse on every delta | H | L | `src/gateway/protocol.py` |
| 3 | **Cron slot state: no replay, advance-past on stop** — track completed slots in store, advance cursor on clean stop | H | M | `src/cron/scheduler.py`, `src/cron/store.py` |
| 4 | **Provider response-header deadline** — add connect/header timeout distinct from read timeout | M | L | `src/engine/llm/provider.py` |
| 5 | **Gateway async DB** — move memory + session SQL off the request handler coroutine | H | H | `src/gateway/session.py`, `src/gateway/server.py`, `src/engine/memory/manager.py` |

---

## Spike picks

**Primary: Tool descriptor caching (`src/engine/tools/registry.py`)**
Every turn currently rebuilds tool descriptors from scratch. Caching the schema dict per registered tool (invalidated only on tool re-registration or config change) is a contained, testable change with a measurable per-turn latency benefit — especially relevant as Lexicon's tool count grows.

**Secondary: Cron slot advancement (`src/cron/scheduler.py`, `src/cron/store.py`)**
The "phantom replay on restart" failure is easy to hit once cron jobs are running in production. Tracking completed slot timestamps in `store.py` and checking them at scheduler startup costs a small amount of schema work but eliminates a class of double-execution bugs.

**Defer: Gateway async DB**
High value but requires threading or async-context changes across gateway + memory layers. Worth a design pass before touching code.
