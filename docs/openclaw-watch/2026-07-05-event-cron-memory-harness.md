# OpenClaw Watch — 2026-07-05

Baseline was 2026.5.27 (stable) / 2026.5.28-beta.2 (beta).

---

## What shipped

### Stable: 2026.6.11 — June 30, 2026
Headline: "rough edges that make OpenClaw feel less dependable." Focus on reliability, not features.

- **Event-driven cron (`on-exit`)** — new schedule kind that fires a job when a watched command exits, rather than on a fixed time trigger. Session-targeted runs can also detach cleanly.
- **Memory/CPU overhead reduction** — long responses, busy tool streams, and memory recall now consume less CPU and filesystem I/O; no configuration required.
- **Gateway restart agent availability** — gateway restarts no longer leave configured agents (Codex, Copilot, trusted plugins) temporarily unavailable; untrusted workspace plugins remain blocked from self-activation.
- **External harness attachment (`openclaw attach`)** — attaches an external harness process to an existing Gateway session for interactive inspection and resume of in-flight runs.
- **GPT-5.6 model support** — recognized across catalog, capability routing, and runtime selection.
- **Multi-channel delivery fixes** — reconnect and reply routing across Telegram, WhatsApp, Matrix, Google Chat, iMessage, Feishu, Mattermost, WebChat, Control UI, terminal UI.

### Beta: 2026.7.1-beta.2 — July 5, 2026
Headline: Codex workflow pairing + `openclaw attach` stabilization + in-flight job warnings.

- **In-flight job doctor** — warns when a cron job's next scheduled fire arrives while the previous run is still executing; prevents silent queue pile-ups.
- **iMessage native polls** — channel-level UI primitive (not relevant to Lexicon).
- **iOS visual modernization + expanded localization** — client-only.
- Carries all 2026.6.11 features into the beta channel.

---

## What's notable (patterns worth watching)

### 1. Event-driven cron: `on-exit` schedule kind
A cron job can now watch a subprocess or external command and fire its agent action the moment that process exits. This is distinct from time-based or interval triggers — it lets scheduling respond to real events (a build finishing, a pipeline completing, a prior agent run wrapping up). The trigger is reactive, not polling.

### 2. Memory recall overhead reduction
OpenClaw reduced CPU and filesystem overhead in the memory recall path without any user-facing config changes. The pattern is to reduce allocations during the recall fan-out and defer filesystem writes until after the agent turn completes, rather than writing synchronously per-interaction.

### 3. Gateway restart agent rehydration
The fix ensures that all configured agent personas are re-registered and available immediately after a gateway restart, with no re-connect window where they'd appear offline. This is a lifecycle correctness pattern: the startup sequence must re-establish agent state before accepting connections.

### 4. In-flight job doctor (consecutive-run guard)
When a cron job's next fire time arrives and the previous run hasn't finished, the system now emits a warning rather than blindly enqueuing a second run. This prevents silent backlog build-up under slow or stuck jobs.

### 5. External harness attachment
A new `openclaw attach` command connects an external process to an already-running Gateway session, giving it access to the live conversation state and tool context. The pattern is "session as an attachable service" rather than a process-lifetime singleton.

---

## What we can use in Lexicon

Ranked by value/effort. File paths verified to exist.

### 1. `on-exit` event-driven schedule — **HIGH value / LOW effort**
Lexicon's scheduler only supports `"at"`, `"every"`, and `"cron"` trigger types:
- `src/cron/store.py:37` — `CronScheduleConfig.type: Literal["at", "every", "cron"]`
- `src/cron/scheduler.py:138` — `_build_trigger()` switch on `schedule.type`

Port: add `"on_exit"` to the `Literal` in `CronScheduleConfig`, add a `watched_command: str | None` field, and implement a watcher in `_build_trigger` / `_execute_job` (asyncio subprocess + `wait()`, then enqueue). No breaking changes — additive only.

### 2. In-flight job doctor warning — **MEDIUM value / LOW effort**
The job execution path in `src/cron/scheduler.py:177` (`_execute_job`) sets `last_status = "running"` at the start but has no guard for re-entrant fires. The fix is a simple `_running_jobs: set[str]` check at the top of `_execute_job` — if `job_id` is already in the set, log a warning and skip (or queue for after). Pairs well with the existing `consecutive_errors` tracking at line 222.

### 3. Gateway restart agent rehydration — **MEDIUM value / MEDIUM effort**
In `src/gateway/server.py:60` (the `lifespan` function), the `AgentRegistry` is instantiated fresh on every startup at line 73. If any agent has session state or in-flight context that survives across restarts (short-term memory files in `SESSIONS_DIR`), the registry doesn't re-attach to it. The pattern is to check for existing state files in `src/engine/memory/short_term.py` during startup and warm the registry before accepting WebSocket connections.

### 4. Memory recall overhead reduction — **MEDIUM value / MEDIUM effort**
In `src/engine/memory/manager.py`:
- `_summarize_interaction` (line 332) does string truncation only — no async work but produces low-signal summaries that bloat `short_term` faster.
- `store_interaction` (line 181) writes to both `working` and `short_term` synchronously on every turn.

The pattern from OpenClaw is to batch short-term writes and defer them to `flush()` rather than writing immediately per-interaction. This directly maps to decoupling the `short_term.append()` call in `store_interaction` and buffering it.

### 5. External harness attachment — **LOW-MEDIUM value / HIGH effort**
The gateway (`src/gateway/server.py`) exposes no mechanism to attach an external process to a live WebSocket session. A new REST endpoint (`POST /sessions/{session_id}/attach`) that returns a token + WebSocket URL for a second client to join an existing session would cover this. Relevant primarily for local dev and debugging, not production.

---

## Picks for what to spike next

**Spike 1 (recommended): `on-exit` schedule kind in `src/cron/`**
Purely additive change to two files. The use case is immediately relevant: Lexicon's OpenClaw-watch routine itself would benefit from firing after a watched build or pipeline exits rather than on a fixed schedule. Low risk, high payoff.

**Spike 2: In-flight job doctor in `src/cron/scheduler.py`**
Ten lines of code. `_running_jobs: set[str]` as an instance variable, guarded at the top of `_execute_job`, cleared in the `finally` block. Prevents the silent-backlog failure mode under slow agent runs.

**Hold: Memory recall batching**
Real improvement but requires a decision about whether `store_interaction` should be synchronous-by-contract. Worth a design note before coding.

**Skip for now: External harness attachment**
High effort, niche use case, no pressing need in current Lexicon workflows.
