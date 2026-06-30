# OpenClaw Watch — 2026-06-30: Runtime fast-mode, transcript SDK, session identity

Baseline: stable `2026.5.27` / beta `2026.5.28-beta.2`
Previous check: n/a (first run)

---

## What shipped

### Stable — `2026.6.10` (released ~2026-06-10)

Headline: reliability sweep across provider routing, session identity, and transcript tooling.

| Area | Change |
|------|--------|
| Runtime fast-mode | `/fast auto` detects short conversational turns and returns a fast response, then falls back to normal mode (with full visible state) for longer or tool-heavy work. |
| Session transcript SDK | Plugins now read/append/publish/lock the session transcript via a stable SDK contract — file-path identity for transcripts is gone; plugins must use the SDK handle. |
| Session identity isolation | Fixes cross-channel identity bleed: a shared DM session no longer carries the previous channel's identity (status, reactions, threads) after a switch. |
| Provider routing | More reliable routing fallbacks; first-run setup no longer skips the selected provider's credential prompt after a plugin installation. |
| Model catalog | Adds GLM-5.2 and Kimi K2.7 Code with corrected capability flags (no video for kimi-k2.7-code). |

### Beta — `2026.6.11-beta.2` (released ~2026-06-11)

Headline: richer channel control and file-driven operator workflows.

| Area | Change |
|------|--------|
| Channel control | Slack relay mode; native Mattermost `/oc_queue` slash command; per-DM model overrides. |
| Operator CLI | `openclaw agent --message-file` lets operators drive an agent from a file (headless, scriptable). |
| RAFT CLI wake bridge | External processes can wake a sleeping agent session via a CLI bridge without opening a full socket. |
| Plugin distribution | Official plugins fully externalized; bundled icon metadata now available to installed clients. |

---

## What's notable (patterns, not features)

1. **Durable transcript SDK contract (stable)** — OpenClaw decoupled transcript identity from file paths. Plugins get a handle (`TranscriptHandle`) and call `.append()`, `.lock()`, `.publish()` — the implementation can live in memory, on disk, or in a remote store without changing plugin code. This is a proper abstraction boundary, not just a rename.

2. **Short-turn fast-mode auto-detection (stable)** — The runtime classifies each incoming turn before invoking the full LLM loop: short/conversational → fast path (smaller model or cached response); long/tool-heavy → normal path. The key insight is that the *decision* is made per-turn, not per-session, and the visible state (tool results, memory context) is preserved across the switch.

3. **Session identity scoping (stable)** — Sessions now carry an explicit channel-scope token that is cleared on channel switch. This prevents status/reaction/thread references from leaking across conversations. The pattern generalises: any mutable session attribute that is channel-specific should be scoped to the channel context, not the session object.

4. **Per-conversation model overrides via channel (beta)** — Model selection is no longer session-global; the channel layer (DM, Slack, Mattermost) can inject a model override per-message. The router receives the override and applies it for that turn only.

5. **File-driven agent invocation (beta)** — `--message-file` is the headless version of interactive prompting. The agent reads the message, executes, and exits — no persistent socket needed. This is the "cron-friendly agent" pattern.

---

## What we can use in Lexicon (ranked)

### 1. Durable transcript SDK contract
**Value: High / Effort: Medium**

`src/engine/memory/transcript_index.py` currently writes to `vault/transcripts/` using file paths derived from meeting timestamps. If the path scheme changes (vault move, multi-tenant), plugins break. Introduce a `TranscriptHandle` dataclass that wraps the write path; plugins call `handle.append(chunk)` and `handle.publish()`. The index file becomes an implementation detail, not an API surface.

Target file: `src/engine/memory/transcript_index.py`

### 2. Session identity scoping
**Value: High / Effort: Low**

`src/gateway/session.py` manages session lifecycle but there is no explicit channel-scope guard. When a session is reused across different callers (e.g. the same agent re-used for a new meeting), channel-specific state (queue key, agent list, metadata) can bleed. Add a `channel_scope` field cleared on `resume()`/`pause()` boundaries.

Target file: `src/gateway/session.py`

### 3. Per-turn model routing
**Value: Medium / Effort: Low**

`src/engine/llm/router.py` resolves provider + model by persona. Extend the `RouteRequest` to accept an optional `model_override` field. The router applies it for one turn; the persona default is unchanged. This is the minimal version of OpenClaw's per-DM override.

Target file: `src/engine/llm/router.py`

### 4. Short-turn fast-mode detection
**Value: Medium / Effort: Medium**

`src/engine/runtime.py` (the agentic execution loop) runs the same path for every turn. A pre-loop classifier that checks token count + tool-call expectation and routes to a smaller model (e.g. `haiku-4-5` instead of `sonnet-4-6`) for pure Q&A turns would reduce latency and cost for conversational interactions.

Target file: `src/engine/runtime.py`, `src/engine/llm/router.py`

### 5. File-driven headless agent invocation
**Value: Low / Effort: Low**

`src/engine/runner.py` exposes the agent loop. Add a `--message-file` flag to the CLI entrypoint so cron jobs and CI pipelines can invoke an agent without spawning a socket session. Pairs well with `src/cron/scheduler.py`.

Target file: `src/engine/runner.py`, `src/cron/scheduler.py`

---

## My picks to spike next

1. **Session identity scoping** (`src/gateway/session.py`) — low effort, directly prevents a class of bugs that would be hard to debug once Lexicon supports multiple concurrent meetings. Spike: add `channel_scope` field + clear on resume.

2. **Per-turn model routing** (`src/engine/llm/router.py`) — one-field extension to `RouteRequest`, zero risk to existing personas. Unlocks cost optimisation without a larger refactor.

3. **Durable transcript SDK** (`src/engine/memory/transcript_index.py`) — worth a design spike before the vault path is locked in for multi-tenant work.
