# OpenClaw Watch — 2026-10-23: Restart Recovery & Pre-Tool Hooks

## What shipped

| Version | Date | Headline |
|---|---|---|
| **2026.10.6** (latest stable) | 2026-10-22 | Requires Node 24.22.1+/26.12.1+. Data-preserving migrations. Reliable delivery across restarts. Provider resilience. |
| **2026.10.10-beta.3** (latest beta) | 2026-10-21 | Windows reliability, upgrade recovery for agent stores, CLI tool catalog invalidation, cron history fixes. |
| **2026.10.10-beta.2** | 2026-10-19 | Safer multi-file `apply_patch`. `before_tool_call` hooks in standalone exec sessions. Cron history O(n) → O(identity). |
| **2026.10.5** | 2026-10-18 | Large release (2,704 commits, 2,250 PRs); external release notes only. |
| **2026.9.33** | ~Sep 2026 | "Extended-stable" / LTS designation added. |
| **2026.9.7** | ~Sep 2026 | OpenAI Agents API + Sign in with ChatGPT (Beta). Tasks/TaskFlow removed — plugin migration required. |
| **2026.9.5** | ~Sep 2026 | Install plugins without restart. Teams of specialist agents. GPT Live in meetings/calls. |
| **2026.9.2** | 2026-09-05 | GPT-6 Astra async tools, Meta Muse Spark 1.3. |
| **2026.7.1** | 2026-07-13 | Control UI / onboarding overhaul. Updated iOS, Android, macOS apps. |
| **2026.6.8** | 2026-06-16 | GLM-5.2, Claude Haiku 4.5 catalog. Safer tool-schema recovery. |
| **2026.6.6** | 2026-06-12 | Security boundary tightening. Browser and MCP connectivity hardening. |

Previous tracked stable: **2026.5.27** (2026-05-27).
Previous tracked beta: **2026.5.28-beta.2**.

---

## What's notable

### 1. `before_tool_call` hooks in isolated exec sessions (beta.2)
OpenClaw now runs `before_tool_call` plugin hooks in a **standalone exec session** — isolated from the parent agent's context. This prevents a policy hook from inadvertently reading or mutating the agent's working state during enforcement. The hook sees the tool call descriptor and can veto or modify it, but cannot reach back into the runtime.

### 2. Restart-safe run recovery (2026.10.6 / beta.3)
Queued turns, streamed partial replies, and watched child results now survive process restarts. OpenClaw stores in-flight run state in SQLite before yielding to the event loop; on cold start it replays any incomplete turns from the durable queue. Beta.3 also fixes upgrade recovery that restores agent stores for owned plugins.

### 3. Cron history O(identity) scan (beta.2)
The cron maintenance job was rewritten to load full run-history payloads only for rows it actually updates, using run IDs as the scan key. Previously it pulled all history into memory to find what to trim. Now it operates on a lazy identity set, making it safe on large run-history tables without ballooning SQLite worker memory.

### 4. Multi-file patch pre-validation (beta.2)
`apply_patch` now validates **all** target paths and hunks before touching any file. A partial-edit failure previously left some files changed and others not. The new pattern is: validate all → if all pass, apply all; if any fail, apply none.

### 5. Provider retry budget with cache preservation (2026.10.6)
When a rate-limited LLM request retries, the existing prompt-cache entries are preserved and forwarded on the retry. Previously a retry would re-send the full payload, busting the cache and increasing latency. The retry now reuses the cache token and only resends the uncached tail.

---

## What we can use in Lexicon

Ranked by value × effort, each mapped to an existing file.

### 1. `tool:before` hook events — **HIGH value / LOW effort**
**File:** `src/engine/hooks/registry.py`, `src/engine/runner.py`

Lexicon already has a full hook registry with prefix matching (`tool:after:*`). The runner fires `tool:after` but there is no `tool:before` event. Adding a `trigger_hook("tool:before:<tool_name>", {...})` call in the runner before each tool dispatch gives plugin authors a veto/modify point that matches OpenClaw's pattern. The isolated-exec insight is the important nuance: a before-hook that raises should block the tool call; one that mutates the event dict should be sandboxed from the agent's in-memory state.

### 2. Multi-file patch pre-validation — **HIGH value / LOW effort**
**File:** `src/engine/tools/vault_write.py`

The vault_write tool applies writes one file at a time. The OpenClaw pattern (collect all targets → validate all → write all or none) makes batched vault writes atomic. The diff is small: extract a `_validate_targets(paths)` pass, run it before the first open(), and abort early with a structured error listing every failing path.

### 3. Provider retry with cache preservation — **MEDIUM value / MEDIUM effort**
**File:** `src/engine/llm/router.py`, `src/engine/llm/litellm_provider.py`, `src/engine/llm/claude_provider.py`

`PersonaLLMRouter.resolve()` returns a provider instance; there is no retry layer today. The OpenClaw pattern wraps the provider call in an exponential-backoff retry that keeps the `cache_control` / `cache_write_tokens` from the first (failed) attempt and forwards them on retry. For Lexicon this means adding a retry shim in `router.py` or in the individual providers that reuses the prompt-cache header rather than rebuilding the payload.

### 4. Cron run-history pagination — **MEDIUM value / LOW effort**
**File:** `src/cron/store.py`, `src/cron/scheduler.py`

`CronScheduler._execute_job()` increments `total_runs` and writes the full state on each run. There is no history trim. OpenClaw's pattern: store a bounded ring of recent run records (identity → timestamp + status), evict oldest entries by count rather than loading all rows. Adding a `max_history` cap to `CronJobStore` and a trim step in `_execute_job` avoids unbounded growth with no behavioral change.

---

## My picks for what to spike next

1. **`tool:before` hooks** — zero-risk, high payoff. Adds the veto/modify point that several planned Lexicon skills (rate-limit guard, PII scrubber) need. One afternoon spike.
2. **Vault write pre-validation** — prevents the class of half-written-vault bugs we've seen in OpenClaw. Straightforward refactor of `vault_write.py`.
3. **Cron history cap** — easy hardening before run counts grow large. `max_history=200` default in `CronJobStore` is enough.
