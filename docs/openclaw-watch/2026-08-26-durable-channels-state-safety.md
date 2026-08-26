# OpenClaw Watch — 2026-08-26: Durable Channels & State Safety

Checked: 2026-08-26  
Baseline stable: 2026.5.27 | Baseline beta: 2026.5.28-beta.2

---

## What Shipped

| Version | Type | Date | Headline |
|---|---|---|---|
| 2026.8.1-beta.3 | beta | 2026-08-24 | Durable ingress monitors, SQLite backup/restore, GPT-5.6 Sol/Terra/Luna/Ultra |
| 2026.8.1-beta.2 | beta | 2026-08-15 | Secret egress host binding, macOS app profiles, CDP relay compatibility |
| 2026.7.2-beta.7 | beta | 2026-08-02 | Quarantine stores, crash-recoverable snapshots, durable channel delivery, session rewind/branching, push-notification approvals |
| 2026.7.1-2 | stable | 2026-08-04 | npm plugin singleton-array fix (hotfix — not ported) |
| 2026.7.1-1 | stable | 2026-08-04 | Memory Core startup repair, Codex progress replies continue post-delivery |
| 2026.6.34 | extended-stable | 2026-08-08 | Sandboxed routes + trusted DNS, provider fallbacks, durable channel pending-work resumption, safer operator diagnostics |

---

## What's Notable (patterns worth porting)

### 1. Durable channel delivery with pending-work resumption (2026.6.34, 2026.7.2-beta.7)
Gateway channels now survive restarts by serialising in-flight work to a durable store and resuming on reconnect. The beta adds quarantine stores so a poison message doesn't block the queue — it's isolated, logged, and the channel continues.

### 2. Crash-recoverable runtime snapshots (2026.7.2-beta.7)
The agent runtime periodically snapshots execution state (current tool call, queued steps, active memory refs) so a mid-run crash can resume from the last checkpoint rather than restarting the full session.

### 3. Session rewind and branching (2026.7.2-beta.7)
Users can now fork the conversation at any prior turn, creating a branch that shares episodic memory up to the fork point. Internally this is a copy-on-write of the transcript index keyed by branch ID.

### 4. Sandboxed routes and secret egress host binding (2026.6.34, 2026.8.1-beta.2)
Outbound tool calls are now routed through a sandboxed path that enforces a per-session allowlist of trusted hosts. Credentials use a SecretRef that is bound to egress-host at auth time, so the credential can't be used to exfiltrate to an arbitrary host.

### 5. LLM provider fallbacks (2026.6.34)
Provider sessions now have a fallback chain: if a primary provider write fails, the runtime retries through an ordered list of alternates before surfacing the error to the orchestrator. State is preserved across the retry.

---

## What We Can Use in Lexicon

Ranked by value/effort ratio (high value first):

### [HIGH value / LOW effort] Provider fallback chain
**OpenClaw pattern:** Ordered alternate providers; state preserved on retry.  
**Lexicon file:** `src/engine/llm/router.py`  
Currently `router.py` selects a provider but does not retry through alternates on failure. Adding a `fallback_chain` config key and a retry loop around the provider call is a contained change with high reliability payoff.

### [HIGH value / MEDIUM effort] Durable channel pending-work resumption
**OpenClaw pattern:** Channel serialises in-flight work; resumes after restart.  
**Lexicon files:** `src/gateway/session.py`, `src/gateway/server.py`  
Sessions currently lose queued work on restart. The pattern is to persist the outbound queue for a session to a durable store (Lexicon already has `src/feedback/db.py` which could host this) and replay it on reconnect.

### [HIGH value / MEDIUM effort] Poison-message quarantine in channel delivery
**OpenClaw pattern:** Bad messages isolated to quarantine store; channel continues.  
**Lexicon file:** `src/gateway/session.py`  
Today a malformed or crashing message can stall the session. A quarantine side-table (sqlite, alongside `src/feedback/db.py`) with move-and-continue semantics is low-risk and eliminates the entire class of stall bugs.

### [MEDIUM value / MEDIUM effort] Crash-recoverable runtime snapshots
**OpenClaw pattern:** Periodic checkpoint of in-flight tool call + step queue.  
**Lexicon files:** `src/engine/runtime.py`, `src/engine/orchestrator.py`  
The runtime has no checkpoint today. Adding one — even just serialising the current `runner.py` step index and active memory refs to disk — would let long tasks survive process restarts. Effort is medium because step state is not currently serialisable.

### [MEDIUM value / HIGH effort] Session rewind and branching
**OpenClaw pattern:** Copy-on-write transcript fork at a prior turn.  
**Lexicon files:** `src/engine/memory/episodic.py`, `src/engine/memory/transcript_index.py`  
`transcript_index.py` already indexes turns; extending it with a branch pointer and making `episodic.py` aware of branch scope is the core work. High effort because the gateway (`src/gateway/session.py`) and memory manager (`src/engine/memory/manager.py`) both need branch context threaded through.

---

## My picks: what to spike next

1. **Provider fallback chain** — `src/engine/llm/router.py`. Smallest scope, immediate reliability win. One config key + one retry loop. Spike: add `llm_fallback_chain` to `src/shared/config.py` and handle in `router.py`.

2. **Durable channel pending-work** — `src/gateway/session.py` + `src/feedback/db.py`. The infrastructure (SQLite db) already exists. Spike: on enqueue, write message to a `pending_outbound` table; on session reconnect, drain and deliver before accepting new messages.

3. **Poison-message quarantine** — `src/gateway/session.py`. Natural companion to the above; essentially free once the DB write path is in place.
