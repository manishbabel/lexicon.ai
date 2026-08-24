# OpenClaw Watch — 2026-08-24

> Covers releases since baseline (2026.5.27 stable / 2026.5.28-beta.2). Checked: 2026-08-24.

---

## What shipped

### Stable channel

| Version | Date | Headline |
|---|---|---|
| 2026.7.1 | July 2026 | Control UI overhaul, gateway stability, model expansion (GPT-5.6, Tencent Hy3, Meta Muse Spark 1.1), channel delivery reliability |
| 2026.7.1-1 | Aug 4 2026 | Patch: Codex progress replies, memory core startup, WSL state permissions |
| 2026.7.1-2 | Aug 4 2026 | Patch: npm plugin singleton-array metadata from newer clients |
| 2026.6.34 _(ext-stable)_ | Aug 8 2026 | Safer browser/network boundaries; provider fallback with retained session writes; **idempotent channel delivery acks**; operator diagnostics redaction; SQLite checkpoint hardening |

### Beta channel

| Version | Date | Headline |
|---|---|---|
| 2026.7.2-beta.7 | Aug 2 2026 | Quarantine stores + crash-recoverable snapshots; **session rewind / transcript fork**; durable multi-platform channel delivery; structured approvals with push notifications; local llama.cpp inference |
| 2026.8.1-beta.2 | Aug 15 2026 | **Secret egress host binding** per shared-store secret; macOS app profile isolation; plugin install provenance warnings |
| 2026.8.1-beta.3 | Aug 24 2026 | GPT-5.6 reasoning tiers (Sol/Terra/Luna/Ultra); Chrome DevTools Protocol relay; **external gateway lifecycle supervision** with verified restart handoff; SQLite snapshot backup/restore; **shared durable ingress monitors** for channel plugins |

---

## What's notable

### 1. Idempotent channel delivery acknowledgements (2026.6.34)
Channels now stamp each outbound message with a delivery token; on retry the receiver deduplicates by token so retried sends never double-deliver. Simple pattern, immediate resilience gain for any message-passing gateway.

### 2. Session rewind / transcript fork (2026.7.2-beta.7)
The runtime can checkpoint a conversation at any turn and branch a new session from that point — enabling undo-style recovery, A/B prompt experimentation, and supervisor-initiated re-runs without replaying the full history from scratch.

### 3. Secret egress host binding (2026.8.1-beta.2)
Each API key or credential in the shared store declares the exact HTTPS host(s) it may be forwarded to. Any substitution or forwarding to an unlisted host fails closed before plaintext egress. Designed to defeat credential exfiltration via prompt injection or misconfigured routing.

### 4. External gateway lifecycle supervision with verified restart handoff (2026.8.1-beta.3)
Gateway health is now supervised by an external process; on crash or upgrade the supervisor waits for the new instance to pass a health check before cutting traffic over. Eliminates the indefinite-restart-loop failure mode called out in 2026.7.1 release notes.

### 5. Shared durable ingress monitors for channel plugins (2026.8.1-beta.3)
A single lifecycle monitor is shared across all channel plugin instances in the scheduler. One crashing plugin no longer starves the others; the monitor persists across scheduler restarts, giving every channel a durable inbox even under partial failure.

---

## What we can use in Lexicon

_Ranked by value-to-effort. All file paths verified against the current `src/` tree._

### 1. Idempotent delivery acks — **HIGH value / LOW effort**
- **Files:** `src/gateway/session.py`, `src/gateway/router.py`
- **Pattern:** Add a per-message delivery token (e.g. `uuid` keyed on message content + session id) tracked in `session.py`. Router deduplicates before dispatching. No external dependency — a simple in-process dict suffices for a first cut.
- **Why now:** Lexicon's `session.py` currently has no ack tracking; this is a one-afternoon addition that closes a silent double-delivery gap under retries.

### 2. Provider fallback with retained session writes — **HIGH value / LOW effort**
- **Files:** `src/engine/llm/router.py`
- **Pattern:** Before routing to a backup provider, flush any pending context writes (tool results, partial turns) so they survive the failover. Wrap the existing `router.py` dispatch with a write-then-route ordering.
- **Why now:** `llm/router.py` already implements multi-provider routing; this is an additive ordering change, not a structural one.

### 3. Secret egress host binding — **HIGH value / MEDIUM effort**
- **Files:** `src/shared/config.py` (allow-list declaration), `src/engine/llm/provider.py` (enforcement point)
- **Pattern:** Add an `allowed_hosts` field to each LLM provider entry in config. In `provider.py`, assert the target URL hostname is in `allowed_hosts` before making any outbound call; raise a hard error otherwise.
- **Why now:** Security hardening — important before any production deployment and low-complexity to add at the provider call site.

### 4. Session rewind / transcript fork — **HIGH value / MEDIUM effort**
- **Files:** `src/engine/memory/transcript_index.py`, `src/engine/memory/episodic.py`
- **Pattern:** `transcript_index.py` already indexes turns; add a `snapshot(at_turn)` method and a `fork(snapshot)` path that initializes a new `episodic` store from the snapshot. No changes needed to the gateway layer for a first spike.
- **Why now:** Unlocks supervisor retry loops and A/B evaluations that are otherwise blocked on full session re-runs.

### 5. Crash-recoverable memory snapshots — **MEDIUM value / MEDIUM effort**
- **Files:** `src/engine/memory/manager.py`
- **Pattern:** On unexpected shutdown (SIGTERM/SIGKILL handler), flush `working` and `short_term` stores to a quarantine file. On `manager.py` startup, detect and recover the quarantine file before opening the normal store.
- **Why now:** Complements the transcript fork work; prevents context loss on pod restarts in containerised deployments.

### 6. Shared durable ingress monitors — **MEDIUM value / MEDIUM effort**
- **Files:** `src/cron/scheduler.py`, `src/engine/hooks/registry.py`
- **Pattern:** Replace per-hook heartbeat checks with a single lifecycle monitor registered once in `hooks/registry.py` and supervised by the `cron/scheduler.py` tick. One failed hook no longer blocks the scheduler loop.
- **Why now:** The current `scheduler.py` runs hooks serially; a shared monitor also opens the path to parallel hook execution.

### 7. External gateway lifecycle supervision — **MEDIUM value / HIGH effort**
- **Files:** `src/gateway/server.py`
- **Pattern:** Move health checks from inside the gateway process to an external watchdog (could be a lightweight subprocess or an OS-level supervisor). The watchdog performs a `/health` probe before cutting traffic. Requires infrastructure changes (Dockerfile or systemd unit).
- **Why later:** High value for production reliability, but requires sidecar infrastructure — better scoped as a standalone spike after the lower-effort wins ship.

---

## My picks for what to spike next

1. **Idempotent acks in `src/gateway/session.py`** — one afternoon, closes a real gap, zero external dependencies.
2. **Secret egress host binding in `src/shared/config.py` + `src/engine/llm/provider.py`** — security-critical before production; straightforward to add at the call site.
3. **Provider fallback with write retention in `src/engine/llm/router.py`** — additive to existing routing logic; pairs well with the host-binding work since both touch the LLM provider layer.
