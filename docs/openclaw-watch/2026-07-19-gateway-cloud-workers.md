# OpenClaw Watch — 2026-07-19: Gateway Safe-Mode & Cloud Worker Dispatch

## What shipped

| Version | Date | Type |
|---|---|---|
| 2026.7.1 | ~2026-07-08 | **Stable** |
| 2026.6.11 | ~2026-06-11 | Stable (prior) |
| 2026.7.2-beta.3 | 2026-07-18 | Beta |
| 2026.7.2-beta.2 | 2026-07-17 | Beta |
| 2026.7.2-beta.1 | 2026-07-15 | Beta |

**Baseline was:** 2026.5.27 stable / 2026.5.28-beta.2 beta

### 2026.7.1 headline changes
- Gateway crash-loop stabilization: repeatedly failing Gateways enter a stable safe-mode (control-plane-safe mode) instead of restarting indefinitely
- Startup migration sequencing: container migrations run before Gateway readiness; recoverable legacy state no longer blocks startup
- Session reply recovery: reply sessions recover after finalization; chat delivery stays bound to the intended conversation across reconnects
- Model/provider expansion: GPT-5.6, Tencent Hy3, Meta Muse Spark 1.1, broader Claude/Ollama support with guided setup and connection verification before saving
- Channel reliability: Telegram (live progress, topics, account routing, retries), Slack (thread/card/identity/duplicate-prevention), Discord (replies, attachments, reconnects)
- 3,063 contributions from 532 contributors across 2,018 public PRs

### 2026.7.2-beta headline changes
- Cloud workers: session placement, dispatch, and worker-turn routing for remote session execution; Control UI sessions run on cloud workers
- Bounded network calls: explicit cap on outbound calls per turn stops unbounded consumption
- Mobile automation parity: headless Linux nodes expose camera, location, notification capabilities; foreground Voice Wake on Android
- Channel stop controls: Signal stop/approval controls remain responsive during active agent turns; allowlist graceful-degradation bug fixed
- Paired-node coding agent discovery and catalog session creation

---

## What's notable

### 1. Gateway safe-mode on repeated boot failures (2026.7.1)
Gateways that crash on startup now count failures and shift to a "control-plane-safe mode" — a degraded-but-stable state — rather than restarting in a tight loop. Startup, restart, migration, auth, fallback, streaming, and oversized-response failures each have distinct recovery paths. This is a meaningful operational maturity pattern: a Gateway that fails cleanly is recoverable; one that restart-flaps takes the whole service down.

### 2. Pre-readiness migration sequencing (2026.7.1)
Migration/upgrade logic runs before the Gateway signals readiness. Legacy state that is recoverable no longer blocks startup. This prevents half-migrated state from being exposed to incoming requests — a correctness guarantee that Lexicon's startup lifespan currently lacks.

### 3. Session reply recovery across reconnects (2026.7.1)
Agent reply sessions can be recovered after finalization. Chat delivery remains tied to the intended conversation lane even after WebSocket disconnect/reconnect. Currently Lexicon cleans up sessions eagerly on disconnect with no replay mechanism — if a run is in-flight the output is lost.

### 4. LLM provider setup with connection verification (2026.7.1)
Model provider setup now runs a verification call before saving configuration. Bad keys are caught at setup time, not at first inference. Guided onboarding preserves earlier choices if setup is interrupted.

### 5. Cloud worker dispatch pattern (2026.7.2-beta)
Sessions can now be placed on remote cloud workers rather than always running locally. The framework introduces session placement, worker-turn routing, and dispatcher logic. This is the most architecturally novel change in this cycle — early-stage for us, but worth tracking as a pattern for multi-node Lexicon deployments.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified against the current `src/` tree.

### #1 — Gateway safe-mode on repeated boot failures
**Value: High / Effort: Low**

`src/gateway/server.py` — the `lifespan()` function has no crash-recovery logic. If any of the startup steps (tool registry, queue, runner, cron) throw, the process exits and the restart loop begins. Add a boot-failure counter in the lifespan context (or an environment-level counter written to disk) and after N consecutive failures, yield in a degraded safe mode (only `/health` responds, all WS connections get a `503`-equivalent). Prevents the service from cycling indefinitely on a bad deployment.

### #2 — LLM provider connection verification before saving
**Value: High / Effort: Low**

`src/engine/llm/router.py` + `src/engine/llm/provider.py` — the `PersonaLLMRouter` instantiates providers but makes no test call. The `POST /api/settings` endpoint in `src/gateway/server.py:436` saves arbitrary API keys without validation. Adding a lightweight ping (e.g. a cheap models-list or minimal completion call) on the new provider instance before writing to `CONFIG_PATH` would surface bad keys at setup time.

### #3 — Session output recovery on mid-run disconnect
**Value: High / Effort: Medium**

`src/gateway/session.py:89` — `end_session()` immediately removes the agent from the registry on WS disconnect. `src/gateway/server.py:333` calls `remove_output_listeners()` before `end_session()`. If a run is in-flight (queue has work on that lane), the output is discarded. Pattern to port: on disconnect, keep the lane alive for a short grace window, persist buffered output to the session JSONL in `src/engine/runner.py`, and re-attach listeners on reconnect with the same session_id.

### #4 — Pre-readiness migration sequencing in lifespan
**Value: Medium / Effort: Low**

`src/gateway/server.py:60` — the `lifespan()` function currently performs no migration step before services start. As Lexicon's data schema evolves (session JSONL format, cron store, memory store), add a migration pass early in startup before `yield`. The `src/cron/store.py` and `src/engine/memory/` stores are the most likely to need version-aware migration.

### #5 — Bounded network/tool calls per runner turn
**Value: Medium / Effort: Low**

`src/engine/runner.py` — `handle_run()` starts an `AgentRuntime.run()` loop with no cap on how many tool calls can occur in one turn. Add a `max_tool_calls_per_turn` guard (configurable via `src/shared/config.py`) that injects a `stop_reason` if the agent exceeds the budget. Prevents runaway tool loops from blocking the queue lane indefinitely.

---

## Spike picks

**Next spike: #1 — Gateway safe-mode.**
It's one function (`lifespan` in `src/gateway/server.py`), the failure mode is real and nasty (restart-flapping takes the service down), and it requires no new dependencies — just a counter and a conditional yield path.

**Watch: cloud worker dispatch (2026.7.2-beta).**
Too early to port — still in beta and requires worker registration/dispatch infrastructure we don't have. Re-evaluate when it stabilizes in a 2026.7.x stable release. The pattern maps loosely to the `src/engine/registry.py` + `src/cron/scheduler.py` isolation boundary if we ever want remote agent placement.
