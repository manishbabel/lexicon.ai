# OpenClaw Watch — 2026-07-11

**Versions covered:** 2026.6.10, 2026.6.11 (stable); 2026.7.1-beta.1 through 2026.7.1-beta.5 (beta)
**Previous baseline:** 2026.5.27 stable / 2026.5.28-beta.2 beta

---

## What shipped

### Stable

**2026.6.10** — Provider routing and adaptive turn speed
- Agents auto-enter "fast mode" for short conversational turns, revert to full reasoning for longer work.
- Provider failover on overload: GLM/Zhipu routes now fall back gracefully instead of erroring.
- Native reasoning-level selection exposed per-request (not just per-session config).

**2026.6.11** — Channel-level model routing (breaking change)
- Slack relay mode: gateway proxies messages to a Slack relay agent without re-routing through the full runtime.
- Native Mattermost `/oc_queue` command: enqueues a task directly into the engine queue from a channel message.
- **Per-DM model overrides**: each direct-message channel can specify its own model, bypassing the global default. The override lives in channel metadata, resolved at session-open time.

### Beta (2026.7.1)

- `openclaw attach`: connects an external harness to an already-running Gateway session — useful for Codex-style interactive oversight of a live agent.
- **ClawRouter** redesign: dynamic model catalog discovery + per-route token budget reporting.
- Event-driven cron: jobs can be triggered by session-exit in addition to wall-clock schedules; detached sessions can be targeted directly.
- Telegram Codex workflows: `/login` and `/steer` commands pair a Telegram thread to an active Codex run.

---

## What's notable

1. **Per-channel model overrides (2026.6.11)** — The gateway now reads model preferences from channel metadata at session-open time. This decouples channel identity from runtime model selection cleanly; no special-casing in the engine layer.

2. **Adaptive fast/slow mode (2026.6.10)** — The runtime measures turn "weight" (token count + tool calls) and chooses provider tier accordingly. Short conversational replies use a cheap fast model; complex multi-tool turns escalate automatically. Pattern: turn-weight classifier upstream of provider dispatch.

3. **Provider failover on overload (2026.6.10)** — Overload errors now trigger a route-level retry to a fallback provider, not a hard error. The router owns fallback selection, not the caller.

4. **Event-driven cron triggers (2026.7.1-beta)** — Cron jobs can subscribe to session lifecycle events (e.g., `session.exit`) in addition to time schedules. Enables "run this cleanup job when the agent finishes, not at midnight."

5. **External harness attach (2026.7.1-beta)** — `openclaw attach` latches a new harness process onto an existing gateway session. Architecturally this means the gateway session is addressable by ID from outside the process — a named session bus pattern.

---

## What we can use in Lexicon

Ranked by value/effort (high value, low effort first):

### 1. Provider failover on overload — HIGH value / LOW effort
**Where:** `src/engine/llm/router.py`

The LLM router already has a `provider` abstraction. Adding a fallback list and catching overload-class errors (HTTP 429/503) to retry on the next provider in the list is a small delta. Prevents hard failures when a provider is rate-limited.

### 2. Per-session model override resolved at session-open — HIGH value / MEDIUM effort
**Where:** `src/gateway/session.py`, `src/gateway/router.py`

Lexicon's gateway creates sessions but currently uses a global model config. Adopting the pattern of reading a model hint from the session/channel metadata at open-time (and passing it into the engine's llm router) unlocks per-workspace or per-channel model customization without touching the engine.

### 3. Adaptive turn-weight → provider tier selection — MEDIUM value / MEDIUM effort
**Where:** `src/engine/runner.py`, `src/engine/llm/router.py`

The runner already orchestrates tool calls and turn execution. Adding a lightweight "turn weight" estimate (output token budget + tool count from the plan) to select between a fast model and a capable model per turn is a natural extension of the existing router.

### 4. Event-driven cron triggers (session lifecycle hooks) — MEDIUM value / MEDIUM effort
**Where:** `src/cron/scheduler.py`, `src/gateway/session.py`

The cron scheduler currently only supports wall-clock triggers (`src/cron/defaults.py`). Adding a simple event subscription so jobs can fire on `session.exit` or `session.complete` would enable post-session cleanup and summary jobs.

### 5. Named/addressable gateway sessions — LOW value now / HIGH effort
**Where:** `src/gateway/server.py`, `src/gateway/session.py`

The external harness attach pattern requires sessions to be addressable by stable ID from outside the process. Lexicon's sessions exist but aren't yet externally addressable in this way. Worth tracking but not a near-term spike.

---

## My picks to spike next

**Spike 1 (this sprint): Provider failover in `src/engine/llm/router.py`**
Small change, high reliability payoff. Catch 429/503 from a provider, rotate to next in a configured fallback list, retry once. No interface changes needed.

**Spike 2 (next sprint): Per-session model override in `src/gateway/session.py`**
Read an optional `model` field from session metadata at open-time, inject into the llm router for that session's lifetime. Unlocks per-workspace model selection for the three agent workspaces in `workspaces/`.
