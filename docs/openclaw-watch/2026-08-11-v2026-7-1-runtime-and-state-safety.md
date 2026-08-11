# OpenClaw Watch — 2026-08-11

Covers stable **2026.6.34 → 2026.7.1-2** and beta **2026.5.28-beta.2 → 2026.7.2-beta.7**
(baseline was 2026.5.27 stable / 2026.5.28-beta.2 beta).

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.7.1 | Aug 4 | stable | Runtime and onboarding overhaul (3 063 contributions, 532 contributors) |
| 2026.7.1-1 | Aug 4 | stable-patch | Memory core startup fixes, Codex progress replies, WSL permissions |
| 2026.7.1-2 | Aug 4 | stable-patch | Plugin update: accept singleton-array metadata from newer npm clients |
| 2026.6.34 | Aug 8 | extended-stable | Security and reliability maintenance; channel delivery stability; operator diagnostics |
| 2026.7.2-beta.7 | Aug 2 | beta | State safety, durable channel delivery, session rewind/branching, MCP Apps, local inference |

**2026.7.1** is the headline stable release. **2026.7.2-beta.7** is the most architecturally significant beta in the series (beta.5–7 share the same feature set; beta.7 is the current tip).

---

## What's notable

### 1. Crash-durable state writes (beta.7)
Three-layer approach: a *quarantine store* that isolates writes from the live database during risky operations; atomic *crash-recoverable SQLite snapshots* (write-to-tmp, fsync, rename); and *schema-upgrade data-loss rejection* that refuses migrations that would destroy rows. Transcript indexes are committed before eviction so eviction never creates a gap. Protects against the most common cause of corrupt agent state: power loss or SIGKILL mid-write.

### 2. Event-conditioned scheduler wake (2026.7.1)
"Scheduled work can wake only when something changes." Interval jobs now carry an optional *condition expression* evaluated before dispatch; if the condition is false (nothing changed since last run), the job tick is a no-op. Eliminates spurious agent runs from heartbeat-style jobs.

### 3. Gateway crash-loop prevention (2026.7.1)
Repeatedly failing gateways no longer restart indefinitely. A stable *repair path* is exposed so operators can diagnose the root cause while the gateway stays in a degraded-but-stable state. Provider startup, auth, streaming, and model-discovery failures all hit the same repair path rather than a hard panic.

### 4. MCP tool call safety — timeout, cancellation, broken streams (2026.7.1)
MCP calls now handle cancellation tokens, per-call timeouts, and mid-stream disconnects without hanging the calling agent. Previously a stalled MCP server could freeze the entire agent loop.

### 5. Dead-letter recovery for channel delivery (beta.7)
Durable channel delivery via a *shared ingress drain* and *dead-letter queue* on Telegram, Signal, Slack, Discord, QQ Bot, IRC, and others. Messages survive gateway restarts; the drain is replayed on reconnect. This is the channel analog of a message broker's persistence guarantee.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified against the repo tree.

### A. Atomic episodic JSONL writes
**Value: High / Effort: Low (minutes)**
File: `src/engine/memory/episodic.py`

`EpisodicMemory.append()` (line 66) uses `open(path, "a")` with no atomic guarantee. A kill mid-write leaves a partial JSON line that silently corrupts the file; subsequent reads skip entries or raise `json.JSONDecodeError`. The fix is the OpenClaw pattern: write to `<file>.tmp`, `fsync`, then `os.rename()`. POSIX rename is atomic; if the process dies before rename the tmp is ignored on next read.

### B. Tool call timeout + cancellation
**Value: High / Effort: Low (< 1 hour)**
File: `src/engine/tools/registry.py`

`ToolRegistry.wire_into_runtime()` (line 59) hands raw handler callables to the runtime with no timeout guard. A hung external tool (e.g. `rss_fetch`, `web_search`, `paper_fetch` — all in `src/engine/tools/`) stalls the agent until the HTTP library times out, which can be minutes. Adding `asyncio.wait_for(handler(**args), timeout=cfg.tool_timeout_s)` in the registry wrapping step gives uniform protection across all tools without touching individual handlers.

### C. Event-conditioned cron jobs
**Value: Medium / Effort: Low-Medium (half day)**
File: `src/cron/scheduler.py`, `src/cron/store.py`

`CronScheduler._execute_job()` (line 177) fires unconditionally on every APScheduler tick. The OpenClaw pattern adds an optional async `condition` callable to the job definition; `_execute_job()` awaits it and skips dispatch if it returns `False`. Concretely, Lexicon's blog-watcher and RSS jobs (`src/cron/defaults.py`) run on an interval even when no new content has arrived. A `condition=has_new_rss_items` guard would cut unnecessary agent invocations.

### D. Provider fallback chain in LLM router
**Value: Medium / Effort: Medium (half day)**
File: `src/engine/llm/router.py`

`PersonaLLMRouter.resolve()` (line 43) raises immediately on auth errors (`ValueError`, `RuntimeError`). OpenClaw's 2026.7.1 pattern keeps a per-persona `fallback_provider` that is tried once before surfacing the error. For Lexicon: if the configured Anthropic key is invalid, fall back to `litellm` (which the provider cache at line 75 already knows how to construct) rather than crashing the agent run.

### E. Gateway error-path stability
**Value: Medium / Effort: Medium (1 day)**
File: `src/gateway/server.py`

The WebSocket handler (line 169) catches `WebSocketDisconnect` and generic `Exception` but has no tracking of per-connection failure streaks. If `_router.dispatch()` throws repeatedly on the same connection, the finally block cleans up correctly but the outer loop doesn't exist; each new connection starts from zero. Following the OpenClaw repair-path pattern: add a consecutive-error counter per `conn_id`; after N failures on the same session, close the WebSocket with a diagnostic message rather than silently absorbing errors.

---

## My picks — what to spike next

1. **A (atomic episodic writes)** — smallest change, eliminates data-loss risk on agent crash. Should be merged before the next release.
2. **B (tool timeout)** — one wrapper in `ToolRegistry.wire_into_runtime()` protects every tool. Immediate UX fix for "stuck agent" reports.
3. **C (event-conditioned cron)** — medium work but enables Lexicon's interval jobs to be genuinely event-driven rather than time-driven; foundational for a smarter heartbeat architecture.
