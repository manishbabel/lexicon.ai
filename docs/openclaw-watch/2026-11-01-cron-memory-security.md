# OpenClaw Watch — 2026-11-01

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.10.10-beta.5** | 2026-10-30 | beta | Cron catch-up, streaming stall fixes, memory ranking, security hardening |
| **2026.10.9** | 2026-10-29 | **stable** | Security deps, workspace tool boundaries, SQLite recovery, rollback safety |
| **2026.9.36** | 2026-10-29 | stable (extended) | Workspace restrictions to gateway tools, bounded untrusted input, npm rollback fix |
| 2026.10.10-beta.4 | 2026-10-27 | beta | Follow-up authority, hooks isolation, memory wiki, session management |
| 2026.10.8 / 2026.10.7 / … | Oct 2026 | stable/beta | Incremental fixes (no separate analysis) |

Previous stable: **2026.5.27** · Previous beta: **2026.5.28-beta.2** · Last checked: 2026-09-23

---

## What's notable

### 1. Cron catch-up after restarts (beta.5 / scheduling)

Cron no longer silently drops missed slots when the stored `next_run` time is stale after a restart. Startup catch-up runs are now admitted, and explicitly disabling a job cancels forced-paused runs. This closes a class of lost-job bugs that appear quiet in logs because nothing errors — work just never fires.

### 2. Semantic-over-keyword retrieval ranking (beta.5 / memory)

Retrieval now ranks closer semantic matches above weak keyword matches. Additional defensive measures: recall pauses after repeated timeouts rather than hammering a degraded index, and cache growth is bounded during index rebuilds. Together these prevent the "expanding index wedges the agent" failure mode.

### 3. Workspace-scoped tool boundaries (2026.10.9 / 2026.9.36 / security + gateway)

`workspaceOnly` is now propagated to gateway-built delegate and media tools — not just natively registered tools. Symlinked workspace skill roots are audited. Unresolved allowlist entries grant nothing instead of opening access broadly. This tightens the security boundary that separates workspace files from agent-constructed tools.

### 4. Credential redaction in logs and process args (2026.10.9 / security)

MCP CLI inspection no longer exposes live credentials. Google OAuth client secrets are masked in logs. Credentials are explicitly scrubbed from process arguments. This is a defense-in-depth pattern: secrets sometimes slip into structured logs via debug paths even when the primary path is clean.

### 5. Monotonic clock for all timeouts (beta.5 / runtime + scheduling)

Timeouts and deadlines across many subsystems were moved from wall-clock to monotonic clock. The fix closes the class of timeout failures caused by NTP adjustments, DST changes, or container clock skew — all of which look like spurious hangs or unexpected expiries in production.

---

## What we can use in Lexicon

Ranked by value / effort (files verified to exist under `src/`):

### 1. Cron catch-up on startup · HIGH value / LOW effort
**Pattern:** On scheduler startup, compare each job's `next_run` against `now`. If it is in the past by more than one interval, emit a catch-up run immediately (or log it skipped, by policy) rather than waiting until the next scheduled slot.

**Files:**
- `src/cron/scheduler.py` — add catch-up pass in the startup sequence
- `src/cron/store.py` — read/update `next_run` in the recovery path
- `src/engine/heartbeat.py` — verify heartbeat isn't suppressing startup catch-up

**Why now:** Lexicon cron likely shares the same silent-drop bug. Low effort because the logic is one guard on the startup loop.

---

### 2. Semantic-over-keyword retrieval ranking · HIGH value / MEDIUM effort
**Pattern:** When memory search returns candidates, sort by embedding similarity score before applying keyword-match boosting — not the other way around. Add a timeout circuit-breaker that pauses recall after N consecutive timeouts and logs a degraded-index warning.

**Files:**
- `src/engine/memory/search.py` — re-order scoring pipeline; add timeout counter + pause guard
- `src/engine/memory/manager.py` — propagate degraded-index state to callers

**Why now:** Keyword-first ranking works poorly on short or semantically dense queries (exactly what Lexicon agents produce). Medium effort due to needing a scoring pipeline refactor.

---

### 3. Credential redaction in logger · MEDIUM value / LOW effort
**Pattern:** Scrub known-secret key names (e.g. `api_key`, `token`, `secret`, `password`, `client_secret`) from any dict/kwargs before they reach a log call. Apply at the log-call site or as a structlog processor.

**Files:**
- `src/shared/logger.py` — add a `redact_secrets` processor/filter

**Why now:** Lexicon logs LLM provider configs (see `src/engine/llm/router.py`, `src/engine/llm/claude_provider.py`). A debug log statement carrying provider kwargs will include credentials. One-day fix.

---

### 4. Workspace-scoped tool boundary enforcement · MEDIUM value / MEDIUM effort
**Pattern:** Tools created at runtime (e.g. via `route_to_agent` or skills dispatch) should inherit the workspace restriction of the session that created them, not bypass it by virtue of being dynamically constructed.

**Files:**
- `src/engine/tools/registry.py` — carry `workspace_root` into dynamically registered tools
- `src/gateway/server.py` — enforce workspace scope on tool results returned to the gateway
- `src/engine/tools/route_to_agent.py` — verify it does not escape workspace bounds

**Why now:** As Lexicon grows agent-to-agent routing, this boundary matters. Medium effort to audit and propagate the scope.

---

### 5. Monotonic clock for cron/timeout logic · MEDIUM value / LOW effort
**Pattern:** Replace `datetime.now()` / `time.time()` in timeout and next-run comparisons with `time.monotonic()`. This only applies to elapsed-time calculations, not calendar scheduling.

**Files:**
- `src/cron/scheduler.py` — timeout and backoff calculations
- `src/engine/queue.py` — any deadline math

**Why now:** Low-cost defensive fix. Worth doing together with item 1 above.

---

## My picks for what to spike next

1. **Cron catch-up + monotonic clock** (items 1 + 5) — pair them in a single PR: same files, low risk, directly improves reliability of Lexicon's scheduled jobs.
2. **Credential redaction** (item 3) — one afternoon, closes a real exposure path.
3. **Semantic ranking + timeout guard** (item 2) — the highest-leverage memory improvement; spike on a branch since it touches the scoring pipeline.
