# OpenClaw Watch — 2026-07-30: Durability Sprint

## What Shipped

### 2026.7.1 — Stable (July 13, 2026)
3,063 commits · 2,018 PRs · 532 contributors

Headline: **Control UI overhaul, multi-platform app releases, expanded provider support.**

Architecture-relevant changes:
- Gateway crash loop prevention and improved startup/restart cycles with enhanced fallback mechanisms
- Session checkpoint consistency and cross-session state persistence improvements
- Transcript handling correctness fixes
- Credential protection hardening, approval scope restrictions, and malformed-input rejection across tools

### 2026.7.2-beta.5 — Pre-release (July 28, 2026)
3,908 merged PRs · a5b2e41..1d326e4

Headline: **Reliability-focused sprint — data durability, durable channel delivery, session branching, cron correctness.**

Architecture-relevant changes:
- **Quarantine store** that survives primary-database damage; crash-recoverable SQLite snapshots with WAL verification; schema-upgrade data-loss rejection; rollback-writer snapshot recovery
- **Durable channel delivery**: shared ingress drain and dead-letter recovery across gateway restarts for Telegram, Signal, Slack, Discord, WhatsApp, IRC and others
- **Session rewind/branching**: fork conversations from individual messages, switch transcript branches in web and native apps, branch-safe queued sends, restore prompt images after fork
- **Cron reliability**: restore one-shot and startup catch-up jobs; preserve cron script state across restarts; unblock completed jobs stuck behind slower batches
- **Provider reliability**: honor Anthropic `Retry-After` headers; prevent false Codex exhaustion; stabilize Ollama/LM Studio local-model discovery; recover Codex Computer Use routes
- **Security**: prevent channel allowlists from granting owner access; close forged-marker/web-search boundary bypass; harden secret redaction; keep session exports inside workspace

---

## What's Notable

### 1. Crash-recoverable SQLite snapshots with quarantine
OpenClaw now publishes session snapshots atomically and quarantines the store if primary-database damage is detected — surviving restarts without data loss even if a write was interrupted. This pattern is a step beyond journaling: the quarantine boundary means a corrupted primary store never silently poisons downstream reads.

### 2. Dead-letter channel delivery across gateway restarts
Messages accepted by the gateway are drained to a persistent ingress buffer before they can be processed. On crash or restart, the drain replays unacknowledged messages rather than losing them. This is the standard "at-least-once delivery" idiom applied to an agent gateway layer.

### 3. Cron one-shot catch-up on startup
Jobs scheduled as one-shot or startup-triggered that were missed during a downtime window are replayed on the next boot. Completed jobs are unblocked even when slower batch jobs are queued in front of them — preventing priority inversion in the scheduler.

### 4. Anthropic `Retry-After` header compliance
Provider calls now inspect the `Retry-After` header on 429 responses and back off for the server-specified duration instead of retrying on a fixed interval. Eliminates thundering-herd storms after rate-limit windows.

### 5. Session branching with branch-safe queued sends
Forking a conversation at an arbitrary message preserves queued tool-call replies and in-flight sends — no orphaned responses leaking into the wrong branch. This is a state-machine correctness guarantee, not just a UI affordance.

---

## What We Can Use in Lexicon

Ranked by value/effort. Each entry maps to a real file in `src/`.

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---------|-------|--------|-----------------|
| 1 | **Anthropic `Retry-After` honor** — On 429, read `Retry-After` header and sleep that duration instead of a hardcoded backoff | High | Low | `src/engine/llm/claude_provider.py` |
| 2 | **Cron startup catch-up** — On boot, replay any one-shot/startup jobs whose scheduled window was missed; unblock queued jobs behind stuck batches | High | Low | `src/cron/scheduler.py`, `src/cron/store.py` |
| 3 | **Dead-letter gateway delivery** — Buffer accepted messages to a durable store before processing; replay on restart instead of dropping | High | Medium | `src/gateway/session.py`, `src/gateway/server.py` |
| 4 | **Memory snapshot quarantine** — Publish memory checkpoints atomically; quarantine the store if schema validation fails on load; prevent corrupt state from poisoning reads | Medium | Medium | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py` |
| 5 | **LLM router Ollama discovery stabilization** — Re-probe local endpoints on startup failure rather than marking them permanently unreachable | Low | Low | `src/engine/llm/router.py`, `src/engine/llm/litellm_provider.py` |

**Security note**: The channel-allowlist-to-owner-access bypass (`src/gateway/router.py`) and session export workspace confinement (`src/gateway/session.py`) are worth reviewing against Lexicon's gateway — even if OpenClaw's surface area is larger, the same shape of bug can exist in simpler implementations.

---

## My Picks for What to Spike Next

**Spike 1 — `Retry-After` in `claude_provider.py` (1–2 hours)**
The fix is a one-liner in the HTTP error handler: parse `response.headers.get("Retry-After")` and pass it to the backoff sleep. This has an outsized reliability impact for any deployment hitting Claude rate limits. Start here.

**Spike 2 — Cron startup catch-up in `scheduler.py` + `store.py` (half day)**
`src/cron/store.py` presumably tracks last-run timestamps. The pattern is: on scheduler boot, compare each job's `next_run` against `now`; if `next_run < now` and the job is one-shot or startup-triggered, run it immediately. For batch jobs, also check for completions blocked behind slower peers. This closes the "missed jobs during downtime" gap cleanly.

These two spikes together cover the highest-value, lowest-effort items and harden Lexicon's two most failure-prone layers (LLM calls and cron) with patterns that OpenClaw has already validated across thousands of deployments.
