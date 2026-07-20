# OpenClaw Watch — 2026-07-20

Baseline: stable `2026.5.27` / beta `2026.5.28-beta.2`
Current:  stable `2026.7.1`  / beta `2026.7.2-beta.3` (July 18 2026)

---

## What Shipped

| Version | Date | Headline |
|---|---|---|
| 2026.6.1-beta.3 | ~Jun 3 2026 | SQLite-first state migration; Skill Workshop governance framework |
| 2026.6.6 | Jun 6 2026 | Authorization fail-closed hardening; compaction timeout cut 900 → 180 s; embedding batch writes |
| 2026.6.11 | Jun 11 2026 | Delivery/reconnect fixes across 9 channels *(hotfixes only, not port-worthy)* |
| 2026.7.1 | Jul 2026 | Control UI overhaul; onboarding-as-agent-loop; provider expansion (GPT-5.6, Hy3, Muse Spark 1.1) *(UI/model additions, not port-worthy)* |
| 2026.7.2-beta.3 | Jul 18 2026 | External gateway supervision mode; Skill Workshop history-scan proposals; terminal session resumption; Android/Linux native automation |

---

## What's Notable (3–5 Patterns)

### 1. SQLite-first state persistence (2026.6.1-beta → 2026.6.6)
Critical mutable state—cron jobs, plugin install indexes, inbound channel queues, iMessage monitor state, Discord thread bindings—migrated from flat JSON/filesystem to SQLite. Concurrent `awatch` + `write` races that produced `SQLITE_BUSY` errors are now serialized per store. `TransientFileProvider`-backed reads retry automatically. Embedding operations batch across files rather than one write per item.

### 2. Skill Workshop governance — proposals, approvals, quarantine, rollback (2026.6.1-beta.3)
New proposal flow with versioned YAML frontmatter, scanner safeguards, and rollback metadata. A `skill_workshop` agent tool applies, rejects, or quarantines proposals through a guarded review flow before the skill becomes active. Disabled skills no longer leak `apiKey` SecretRefs into embedded turns—secret refs are masked at index time.

### 3. Authorization fail-closed at every security boundary (2026.6.6)
Transcript, sandbox, MCP, browser, channel, and exec-approval paths now explicitly fail closed on: (a) unsafe access attempts, (b) timed-out approvals, (c) malformed boundary input. Rustup and git protocol environment overrides blocked. Non-owner loopback tools restricted. MCP stdio filtered for malformed tool definitions.

### 4. Compaction timeout reduction + per-session ownership (2026.6.6)
Default LLM compaction timeout dropped from 900 s to 180 s, with explicit config override supported. Context-engine compaction ownership is now preserved per agent/Codex session so concurrent sessions don't clobber each other's compaction state.

### 5. External gateway supervision mode (2026.7.2-beta.3)
A new `--supervised` flag (or env var) signals the gateway to delegate process lifecycle to an external supervisor. Enables clean crash-loop recovery, structured restart coordination, and `SIGTERM` hand-off without data loss. Auth profiles write atomically with force-relogin recovery, and workspace state survives state-only uninstall.

---

## What We Can Use in Lexicon (ranked value / effort)

### A. Add compaction timeout + configurable override ★★★ value / ★ effort
**File:** `src/engine/context/compactor.py`

`_generate_summary()` has no timeout. If the LLM hangs, the compactor blocks the entire context pipeline indefinitely. Wrapping the call in `asyncio.wait_for(self._generate_summary(...), timeout=COMPACTION_TIMEOUT_S)` with a fallback to `_fallback_compact()` matches OpenClaw's pattern exactly. `COMPACTION_TIMEOUT_S` defaults to `180`, read from `src/shared/config.py`. One-hour spike.

### B. SQLite cron store to eliminate read-modify-write races ★★★ value / ★★ effort
**File:** `src/cron/store.py`

Current store does `load()` → mutate → `save()` (full JSON rewrite) on every `update_state()` call. Under concurrent APScheduler job firing this is a race: two jobs reading the same `jobs.json` simultaneously, then both writing back, last-write-wins. Replacing with a lightweight SQLite backend (one table: `cron_jobs`, columns mirroring `CronJob` fields, state stored as JSON blob or individual columns) eliminates this. `src/cron/scheduler.py` and `src/cron/defaults.py` need only minor adapter changes—the `CronJobStore` interface stays the same.

### C. Fail-closed authorization boundaries in tool registry and gateway ★★ value / ★★ effort
**File:** `src/engine/tools/registry.py`, `src/gateway/server.py`

Audit all error paths in tool dispatch and WebSocket session handling. Anywhere a timeout, permission check, or schema validation currently silently degrades (returns empty, logs a warning, continues) should instead raise explicitly so the caller can surface the refusal. Specifically: tool execution timeout should close the tool call with an error rather than hanging; MCP tool schema validation failures should reject at registration time, not at call time.

### D. Skill secret isolation for disabled skills ★★ value / ★ effort
**File:** `src/engine/skills.py`

`_parse_skill_dir()` reads full SKILL.md frontmatter into `SkillDefinition`. If a skill is disabled (e.g., via a `enabled: false` frontmatter key we don't currently support), its metadata—including any `apiKey` or credential references—still flows into `get_metadata()` and ultimately into system prompt context. Add a `enabled` frontmatter check in `_parse_skill_dir()` and strip credential-pattern fields before indexing disabled skills.

### E. Cron retry on transient rate-limit before next slot ★★ value / ★★ effort
**File:** `src/cron/scheduler.py`

When an agent job fails due to a model rate-limit error (HTTP 429 / `RateLimitError`), the current `_execute_job()` records `last_status: "error"` and waits for the next scheduled slot. OpenClaw retries once after a short jitter delay before giving up on the slot. Add a retry wrapper around the enqueue call in `_execute_job()` that catches `RateLimitError`, waits `retry_after` seconds (bounded to ≤ 60 s), and re-enqueues once before recording the error.

---

## My Picks — What to Spike Next

1. **[A] Compaction timeout** (`src/engine/context/compactor.py`) — 1–2 h, zero interface changes, eliminates a real hang risk that grows with LLM latency variance.
2. **[B] SQLite cron store** (`src/cron/store.py`) — half-day, eliminates a real concurrent-write race that becomes visible as soon as two cron jobs fire within the same second.
3. **[D] Skill secret isolation** (`src/engine/skills.py`) — 1 h, small change, closes a credential-leak path before Skill Workshop governance is built on top.
