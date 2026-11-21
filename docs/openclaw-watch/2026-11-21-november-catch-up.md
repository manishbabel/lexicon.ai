# OpenClaw Watch — 2026-11-21

Covers releases from **2026.5.27** (previous stable baseline) through **2026.11.6** (latest stable) and **2026.11.10-beta.1** (latest beta).  Six months of weekly builds condensed to signal-only patterns.

---

## What shipped

| Release | Date | Track | Headline |
|---|---|---|---|
| 2026.11.10-beta.1 | 19 Nov | Pre-release | Agent template packages (ClawHub), scheduled auto-updates, startup state migration, background commands survive Gateway restart |
| 2026.11.6 | 19 Nov | **Latest stable** | Stability and polish roll-up (full notes not yet published) |
| 2026.11.5-beta.4 | 16 Nov | Pre-release | Automation continuity across restarts; Telegram widgets; OpenAI/Claude provider recovery |
| 2026.11.3 | ~10 Nov | Stable | Cron resilience, gateway hardening, LLM provider credential scoping, auth deadline propagation |
| 2026.10.33 | 18 Nov | Extended-stable (LTS) | Bounded session-store memory; event-driven automations (MCP events + polled conditions); on-demand skill search; transcript import |
| 2026.9.37 | Sep | Stable | Earlier patch; notes not captured |
| 2026.9.6 | Sep | Stable | macOS launch crash fixed with rebuilt binary |

Primary source: https://github.com/openclaw/openclaw/releases  
Secondary: https://www.gradually.ai/en/changelogs/openclaw/ (aggregator, some metadata inconsistencies noted)  
`releasebot.io` and `docs.openclaw.ai` are outside this session's allowed network domains; not consulted.

---

## What's notable

### 1. Bounded session-store memory (2026.10.33)
OpenClaw added explicit capacity caps to in-memory session and chat stores to prevent unbounded growth on long-running agents.  Previously, large sessions would grow until the process was OOM-killed.  The fix introduces a configurable high-water mark per session and a background eviction pass that uses an LRU strategy, keeping recent turns hot while aging out older ones.

### 2. Event-driven cron — MCP events and polled conditions (2026.10.33)
Scheduled automations can now fire on *conditions* (a polled value crossing a threshold) or on *events* (an incoming MCP notification) rather than only on time-based cron expressions.  The scheduler polls a lightweight condition-evaluator at a configurable cadence; MCP events are delivered as a push notification that bypasses the polling cycle entirely.

### 3. On-demand skill search (2026.10.33)
Skills are no longer eagerly loaded at Gateway startup.  A registry index is built at boot (name, description, trigger keywords), and the runtime lazy-loads a skill's full definition only when it matches the current context.  Cuts startup time and working-set size proportionally to the number of installed skills.

### 4. Provider auth deadline propagation + credential scoping (2026.11.3)
Two distinct fixes shipped together: (a) provider authentication now respects the per-run deadline and propagates cancellation to in-flight auth handshakes, so a hung OAuth exchange no longer blocks a run indefinitely; (b) cached plugin results and embedding API calls are now scoped to the credentials that produced them and are not served to callers with different credentials.

### 5. Cron store failure isolation (2026.11.3)
A storage write failure in the cron subsystem (e.g., disk full, DB lock contention) no longer kills the Gateway process.  The scheduler catches store errors, logs them with the failing job ID, and continues scheduling.  One-shot job cleanup is deferred rather than lost when the job transitions to recurring.

---

## What we can use in Lexicon

Ranked by estimated value / effort (H = high, M = medium, L = low).

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---|---|---|---|
| 1 | Bounded session-store memory | H | L | `src/engine/memory/working.py`, `src/engine/memory/short_term.py` |
| 2 | Event-driven cron (MCP events + polled conditions) | H | M | `src/cron/scheduler.py`, `src/cron/store.py` |
| 3 | On-demand / lazy skill loading | M | L | `src/engine/skills.py`, `src/engine/registry.py` |
| 4 | Provider auth deadline propagation | M | L | `src/engine/llm/provider.py`, `src/engine/llm/router.py` |
| 5 | Cron store failure isolation | L | L | `src/cron/scheduler.py`, `src/cron/store.py` |

**Notes per item:**

1. **Bounded memory** — `src/engine/memory/working.py` holds the in-process working-memory buffer; `src/engine/memory/short_term.py` holds recent turns.  Neither currently has capacity caps.  Adding a `max_tokens` / `max_items` eviction threshold (similar to the pruner in `src/engine/context/pruner.py`) would prevent long-running agents from ballooning.

2. **Event-driven cron** — `src/cron/scheduler.py` is purely time-triggered today.  Wrapping it with a `ConditionSource` protocol (polled) and a `MCPEventSource` (pushed) would let Lexicon's skills fire reactively — e.g., trigger the blog-watcher when an RSS item arrives rather than on a fixed interval.  `src/engine/tools/rss_fetch.py` and `src/engine/tools/blogwatcher_cli.py` are natural first consumers.

3. **Lazy skill loading** — `src/engine/skills.py` loads skill definitions; `src/engine/registry.py` owns the runtime registry.  An index-at-boot / load-on-match approach would keep startup fast as the workspace skill sets (see `workspaces/*/skills/`) grow.

4. **Auth deadline propagation** — `src/engine/llm/router.py` dispatches to individual provider clients; `src/engine/llm/provider.py` defines the base interface.  Adding a `deadline` parameter to the `complete()` signature and threading it through to the HTTP client timeout would prevent LLM calls from hanging indefinitely after a task is cancelled.

5. **Cron store fault tolerance** — `src/cron/store.py` and `src/cron/scheduler.py` should wrap store writes in a try/except that logs and continues rather than propagating exceptions up to the Gateway entrypoint.

---

## My picks for what to spike next

**Primary: Event-driven cron** (`src/cron/scheduler.py`, `src/cron/store.py`)  
This unlocks the highest leverage shift: Lexicon agents react to real-world signals instead of waking up on a fixed clock.  `rss_fetch.py` and `blogwatcher_cli.py` are ready-made first consumers, so the spike is immediately testable end-to-end without new tools.

**Secondary: Bounded memory** (`src/engine/memory/working.py`)  
One-line guard: cap working memory at a configurable `max_tokens` and delegate overflow to `src/engine/context/pruner.py`, which already implements the eviction logic.  Low effort, high reliability gain for long-running agents.
