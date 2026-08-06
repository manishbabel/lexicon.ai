# OpenClaw Watch — 2026-08-06: State Safety & Session Branching

> Baseline: stable `2026.5.27` / beta `2026.5.28-beta.2`
> Coverage: through stable `2026.7.1-2` (Aug 4) and beta `2026.7.2-beta.7` (Aug 2)

---

## What Shipped

| Version | Date | Headline |
|---|---|---|
| `2026.7.2-beta.7` | Aug 2 | State safety + recovery, session branching, durable channel delivery, structured approvals |
| `2026.7.2-beta.6` | Aug 1 | Same feature set, stabilisation |
| `2026.7.2-beta.5` | Jul 28 | GPT Live via Codex OAuth (not Platform API), meeting transcript collection |
| `2026.7.1-2` | Aug 4 | npm plugin fix: singleton-array metadata from newer clients |
| `2026.7.1-1` | Aug 4 | Codex progress-reply fix, Memory Core startup repair, WSL state-permissions tolerance, legacy migration recovery |
| `2026.7.1` | Jul 13 | Session-first Control UI, ClawRouter dynamic model discovery + budget reporting, reasoning-effort controls, generated session titles |

Skipped as non-pattern: `2026.7.1-1` Codex progress-reply and WSL tweaks are hotfixes; `2026.7.1-2` is a plugin metadata fix.

---

## What's Notable (5 Patterns)

### 1. Crash-Recoverable State via SQLite Quarantine (`2026.7.2-beta.7`)
OpenClaw introduced "state safety and recovery": active session state is periodically snapshotted to SQLite with a quarantine area for in-flight writes. On restart, the agent replays from the last clean snapshot rather than from zero. Previous behaviour (pure in-memory dict) caused full context loss on crash.

### 2. Session Rewind and Branching (`2026.7.2-beta.7`)
Conversations can now be forked from any past message. The fork creates a new session with the parent's context up to that point as its starting state. The parent session is unmodified. Implemented as an immutable linked-list of `SessionSnapshot` objects tagged by message index.

### 3. ClawRouter: Dynamic Model Discovery + Budget Reporting (`2026.7.1`)
The static persona→model config was replaced by ClawRouter, which queries registered providers at runtime for their available models and tracks per-session token spend against a configurable budget. When a persona exhausts its budget, ClawRouter downgrades to a cheaper model tier automatically.

### 4. Durable Channel Delivery (`2026.7.2-beta.7`)
Outbound messages to Telegram, Slack, Signal, etc. are now written to a WAL (write-ahead log) before dispatch. If a delivery fails, the scheduler retries from the WAL rather than re-running the agent. The channel layer decouples generation from delivery.

### 5. Structured Questions and Approvals with Push Notifications (`2026.7.2-beta.7`)
Agents can emit a `StructuredQuestion` event containing a prompt, options, and a deadline. The gateway holds the session, pushes a notification (email/mobile), and resumes the agent with the user's response when it arrives. Replaces the previous pattern of blocking on a live reply.

---

## What We Can Use in Lexicon

Ranked by `value / effort` (high = act soon):

### 1. Session Persistence to SQLite — `src/gateway/session.py` ⬆️ **High value / Low effort**
`SessionManager._sessions` is a plain `dict[str, SessionState]`. A crash wipes every active session with no recovery path. OpenClaw's pattern is a 5-line SQLite upsert on every `create_session` / `update_session` call, plus a `restore_sessions()` call at startup. This is the single most impactful thing we can copy: it directly fixes a crash-data-loss bug in production.

Touch points: `src/gateway/session.py` (add `_persist()` and `_restore()` calls), `src/shared/types.py` (add `snapshot_at` field to `SessionState`).

### 2. Budget Tracking in PersonaLLMRouter — `src/engine/llm/router.py` ⬆️ **High value / Medium effort**
`PersonaLLMRouter.resolve()` always picks the configured model with no spend awareness. OpenClaw's ClawRouter adds a `SpendLedger` (token counts per persona per day) consulted at resolve time. If spend exceeds a per-persona threshold, it steps down the model tier. We already have `AgentConfig.max_tokens` in `src/shared/types.py`; adding a ledger and a downgrade table is incremental work.

Touch points: `src/engine/llm/router.py`, `src/shared/config.py` (budget thresholds), `src/shared/types.py` (extend `AgentConfig`).

### 3. Session Branching — `src/gateway/session.py` + `src/shared/types.py` **Medium value / Medium effort**
`SessionState` has no concept of a parent session or a snapshot anchor. Adding `parent_session_id: str | None` and `branched_from_message_index: int | None` to `SessionState` plus a `branch_session()` method to `SessionManager` would unlock this pattern. Most valuable for the chief and ai-educator personas where users want to explore alternative meeting directions.

Touch points: `src/shared/types.py` (`SessionState`), `src/gateway/session.py` (`branch_session()`).

### 4. WAL-Backed Channel Delivery — `src/gateway/server.py` **Medium value / High effort**
The current gateway sends channel messages inline with agent output streaming. A WAL layer between `src/gateway/server.py` and outbound delivery would decouple generation from reliability. Worth spiking after the SQLite session work since we'll already have SQLite wired.

Touch points: `src/gateway/server.py`, `src/gateway/protocol.py`.

### 5. Structured Approvals via Hooks — `src/engine/hooks/builtin.py` **Medium value / Medium effort**
The hooks system (`src/engine/hooks/`) could emit a `StructuredQuestion` event that the gateway parks and notifies on. Today agents either block or skip. This pattern fits our cron-triggered agents (`src/cron/scheduler.py`) where overnight jobs could ask for approval before taking a destructive action.

Touch points: `src/engine/hooks/builtin.py`, `src/engine/hooks/registry.py`, `src/cron/scheduler.py`.

---

## My Picks for Next Spike

**Spike now:** Pattern 1 — session persistence to SQLite in `src/gateway/session.py`. Five lines of write, five lines of read at startup, and it prevents complete data loss on any unclean shutdown. The work is fully self-contained and reviewable in one PR.

**Spike next:** Pattern 2 — budget ledger in `src/engine/llm/router.py`. We're running multiple personas with different model tiers and have no visibility into per-persona spend. ClawRouter's pattern adds that in one new class and a handful of callsites.

**Watch for stable:** Pattern 3 (session branching) — shipping in beta only. Worth tracking as `2026.7.2` stabilises.
