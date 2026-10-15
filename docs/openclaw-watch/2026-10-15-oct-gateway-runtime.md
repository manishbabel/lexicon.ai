# OpenClaw Watch — 2026-10-15: Gateway & Runtime Resilience

**Digest period:** 2026-09-23 → 2026-10-15  
**Previous stable:** 2026.5.27 | **Previous beta:** 2026.5.28-beta.2

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.10.3** | 13 Oct | Stable (Latest) | Gateway stability + new model support (90 commits, 79 PRs, 99 contributors) |
| **2026.9.33** | 15 Oct | Extended-stable | 2026.9 line hardened: state/plugin-data integrity, unattributed-write protection |
| **2026.10.5-beta.4** | 15 Oct | Beta | macOS/systemd update reliability; context-limit reporting fix; Tlon group-DM security fix |
| **2026.10.5-beta.3** | 13 Oct | Beta | Interrupted turns resume after restarts; stale Telegram spool deduplication (24 h TTL) |

Intervening stable releases since the 2026.5.27 baseline (2026.6.1 through 2026.9.9) are summarised under "What's notable" where they introduced lasting patterns.

---

## What's notable

### 1. Turn resumption after Gateway restart (2026.10.5-beta.3)
Interrupted agent turns are checkpointed and resume automatically when the Gateway comes back up. Prior to this, a restart mid-turn dropped the work on the floor. The pattern is: snapshot turn state to durable storage before executing, reload it on startup, and re-enter the turn loop from the checkpoint. This is distinct from session-level reconnect — it survives a full process death.

### 2. Stale-message deduplication with a 24 h TTL (2026.10.5-beta.3)
Inbound channel messages (Telegram spool) are stamped and tracked; messages older than 24 hours on reconnect are imported as *stale* rather than re-dispatched. Prevents duplicate processing when a channel catches up after downtime. The fence is at the channel ingestion layer, not in each tool handler.

### 3. Unattributed-write protection (2026.9.33)
The system refuses automatic restores over writes that carry no authorship attribution (the "Doctor" unattributed-writes case). Pattern: every write to persistent state must carry an author token; a restore that would overwrite attributed data with unattributed data is blocked and surfaced as an error. Defence against silent state corruption from background jobs.

### 4. State and plugin-data integrity through upgrades (2026.9.33)
Upgrades on the 2026.9 extended-stable line preserve state, plugin data, and service ownership across version transitions. Related earlier work (2026.6.1): the plugin install index, cron persistence, and inbound queues migrated from filesystem scanning to SQLite, making the integrity guarantee feasible.

### 5. Context-limit reporting standardisation (2026.10.5-beta.4)
Context limit reporting unified across runtimes (status panel, Copilot integration, llama.cpp). Previously each runtime computed its own effective limit, leading to inconsistent saturation warnings. The fix centralises limit resolution into a single source and surfaces it through a standard interface.

---

## What we can use in Lexicon

Ranked by **value / effort** (higher value and lower effort = port first).

### A. Turn checkpointing on restart — `src/engine/runner.py`  
**Value: High / Effort: Medium**  
`src/engine/runner.py` currently has no crash recovery; a restart drops in-flight work. Add a checkpoint write before each tool dispatch and a startup scan for abandoned checkpoints. The session queue in `src/engine/queue.py` is the natural place to persist the checkpoint payload.  
*Files:* `src/engine/runner.py`, `src/engine/queue.py`

### B. Stale-message deduplication — `src/gateway/session.py`  
**Value: High / Effort: Low**  
When the gateway reconnects after downtime, it replays buffered messages. Adding a seen-ID set with a 24 h TTL fence in `src/gateway/session.py` stops duplicate tool calls from channel catch-up. The ingestion path in `src/gateway/protocol.py` is where the stamp belongs.  
*Files:* `src/gateway/session.py`, `src/gateway/protocol.py`

### C. Unattributed-write guard — `src/vault/writer.py`  
**Value: Medium / Effort: Low**  
`src/vault/writer.py` currently writes vault entries without an author field. Adding an `author` parameter (required, no default) and a guard that refuses writes with an empty author would catch background-job corruption of the same shape OpenClaw's "Doctor" case exposed.  
*Files:* `src/vault/writer.py`

### D. Centralised context-limit resolution — `src/engine/context/token_counter.py`  
**Value: Medium / Effort: Low**  
`src/engine/context/token_counter.py` maintains token counts per provider. If the effective context window is queried multiple places (`src/engine/llm/provider.py`, `src/engine/context/pruner.py`), the same inconsistency risk exists. Centralising the limit lookup here and having all callers read from one function removes the drift.  
*Files:* `src/engine/context/token_counter.py`, `src/engine/context/pruner.py`, `src/engine/llm/provider.py`

### E. SQLite for cron persistence — `src/cron/store.py`  
**Value: Medium / Effort: Medium**  
`src/cron/store.py` holds the cron job registry. If it uses filesystem state, migrating to SQLite (as OpenClaw did in 2026.6.1) makes job definitions survive restart without a re-scan and enables transactional updates that keep state and schedule consistent.  
*Files:* `src/cron/store.py`, `src/cron/scheduler.py`

---

## My picks for what to spike next

1. **B — Stale-message deduplication** (`src/gateway/session.py`): lowest effort, high payoff, directly defensive against a known reconnect pattern. One seen-ID set with a TTL flush is a half-day spike.

2. **A — Turn checkpointing** (`src/engine/runner.py`): protects in-flight agent work from restarts. Moderate effort but the value is clear and the queue abstraction (`src/engine/queue.py`) gives a natural persistence hook. Worth a focused spike before the next infra change window.

3. **C — Vault unattributed-write guard** (`src/vault/writer.py`): trivial code change, meaningful integrity property. Bundle with the next vault PR.
