# OpenClaw Watch — 2026-09-01

## What shipped

| Version | Date | Headline |
|---|---|---|
| **2026.8.1** (stable) | 2026-08-31 | Background memory consolidation, masked credentials, conversation branching, recurring-approval permissions, startup config validation |
| **2026.9.1-beta.1** (beta) | 2026-08-28 | Gateway restart recovery preserving admitted turns, config write reliability during watcher handoff, worker recovery for delegated work |
| 2026.7.1 (stable, previously unseen) | 2026-07-xx | Control UI overhaul, `openclaw attach` for coding-agent session handoff, stable Gateway restart-loop repair |
| 2026.6.5 (stable, previously unseen) | 2026-06-xx | Channel media reliability (Telegram/Slack/Discord), cross-session transcript dedup |

Previous baseline: stable `2026.5.27` / beta `2026.5.28-beta.2`.

---

## What's notable

### 1. "Grounded dreaming" — model-backed background memory consolidation (2026.8.1)
OpenClaw now runs a background pass that feeds recent episodic memory through the model to surface reusable lessons, storing them with Scanner approval. The Dream Diary provides an audit trail. This is distinct from simple summarisation: the model reasons over the raw transcript chunks, extracts durable facts, and writes them back into a separate long-term store — decoupled from the foreground inference path.

### 2. Masked credential prompts — secrets never enter model context (2026.8.1)
When the agent needs a secret (API key, password), it issues a masked prompt that collects the value out-of-band and injects it only as a substitution token, never as plaintext in the conversation or model input. Proxy rules then restrict which destinations can receive the substituted value.

### 3. Recurring-work approval — per-operation permission grants (2026.8.1)
Users can approve an exact operation once and have that approval persist for identical future invocations. Approvals are inspectable and revocable per operation. This is more granular than blanket tool allowlists: the approval tracks the tool + argument fingerprint.

### 4. Startup config validation & safe migration (2026.8.1)
Gateway now runs "doctor configuration migrations" before normal startup rather than after first request. Startup-blocking config errors surface immediately, and `openclaw doctor --fix` handles automated migrations (e.g. the codex→openai route rename). The external-supervisor mode (`OPENCLAW_SUPERVISOR_MODE=external`) lets an external process own the Gateway lifecycle.

### 5. Conversation branching — fork from any user message (2026.8.1)
Any prior user message can be "rewound" to create a branch while preserving earlier paths. The compaction layer tracks branch heads independently. Useful for multi-path agent evaluation and prompt regression testing.

---

## What we can use in Lexicon

Ranked by **value / effort** (H = High, M = Medium, L = Low). Every file path verified against `src/` tree.

### 1. Masked credential injection — `src/gateway/session.py`, `src/shared/config.py`
**Value: H / Effort: L**

Lexicon's gateway currently passes credentials through the standard message payload. Add a `MaskedParam` type in `src/shared/config.py` that holds a reference token, and resolve it in `src/gateway/session.py` immediately before model dispatch — never earlier. The `src/gateway/router.py` destination allowlist can enforce where substituted values are forwarded. No model-layer changes needed.

### 2. Background memory consolidation pass — `src/engine/memory/manager.py`, `src/engine/memory/episodic.py`
**Value: H / Effort: M**

`src/engine/memory/manager.py` already coordinates episodic and working stores. Add a consolidation coroutine (off the hot path, triggered by the cron scheduler in `src/cron/scheduler.py`) that reads unprocessed chunks from `src/engine/memory/episodic.py`, runs a short model call to extract durable lessons, and writes them to a new `long_term` bucket in the memory manager. The Dream Diary pattern maps to a simple append-only log file per agent — low storage overhead, high debuggability.

### 3. Startup config validation — `src/gateway/server.py`
**Value: H / Effort: L**

Move config validation currently done lazily on first request into an explicit `validate_config()` step at the top of `src/gateway/server.py`'s startup sequence, before accepting connections. Add a migration runner that applies forward-only config patches from a versioned list. Surfaces misconfiguration immediately rather than mid-session.

### 4. Per-operation recurring approval — `src/engine/skills.py`, `src/gateway/router.py`
**Value: M / Effort: M**

Skills declared as `requires_approval=True` in `src/engine/skills.py` today prompt on every invocation. Track a fingerprint (tool name + canonicalised argument hash) in a small SQLite table and skip the prompt for exact matches the user has previously approved. Store the grant list accessibly via `src/gateway/router.py` so the UI can display and revoke entries.

### 5. Context branching hooks — `src/engine/context/compactor.py`, `src/engine/context/pruner.py`
**Value: M / Effort: M**

`src/engine/context/compactor.py` currently compacts into a single linear history. Add an optional `branch_id` field to the compaction record so multiple heads can coexist in the same session store. `src/engine/context/pruner.py` would prune per-branch independently. Enables A/B prompt testing without spawning duplicate agents.

---

## My picks for what to spike next

1. **Masked credential injection** (pattern 1) — highest safety lift for least code. A `MaskedParam` wrapper in `src/shared/config.py` plus injection in `src/gateway/session.py` is a single-PR change that closes a real leak vector.

2. **Startup config validation** (pattern 3) — pure reliability gain, no new dependencies. Lexicon's current lazy validation has caused at least one confusing mid-session failure; moving it to startup makes ops much cleaner.

3. **Background memory consolidation** (pattern 2) — medium spike. Stand up the consolidation coroutine wired to `src/cron/scheduler.py` with a feature flag; measure memory recall quality before enabling by default.
