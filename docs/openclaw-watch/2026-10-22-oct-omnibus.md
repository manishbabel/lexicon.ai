# OpenClaw Watch: 2026-10-22 Digest

**Covers:** 2026.10.5 (stable, 2026-10-18) · 2026.10.10-beta.3 (pre-release, 2026-10-21)  
**Previous baseline:** 2026.5.27 stable / 2026.5.28-beta.2 beta (last checked 2026-09-23)  
**Source:** https://github.com/openclaw/openclaw/releases

---

## What Shipped

| Version | Date | Type | Scale |
|---|---|---|---|
| 2026.10.5 | 2026-10-18 | Stable | 2,704 commits · 2,250 PRs · 638 contributors |
| 2026.10.10-beta.3 | 2026-10-21 | Pre-release | Windows reliability · memory cold-start fix |
| 2026.10.10-beta.2 | 2026-10-19 | Pre-release | apply_patch atomicity · before_tool_call in exec sessions |
| 2026.10.10-beta.1 | 2026-10-15 | Pre-release | SQLite to worker threads · restart-safe replies · PostgreSQL store (exp.) |

### 2026.10.5 Headline Changes

**Architecture / Runtime**  
- DB operations (session setup, history reads, compaction prep, branch listing) moved to background workers; SQLite worker handoffs hardened with memory release after completed requests and shutdown that waits for accepted writes to settle.  
- Managed worktree cleanup runs as background job with global checkout cap and eviction policy; incremental Git maintenance suspends failing repos so others continue.  
- Stalled model-catalog loads now time out with retryable messages instead of hanging.

**Restart / Recovery**  
- Interrupted Control UI turns, worker tasks, and eligible replies resume after a Gateway restart.  
- Restart-interrupted subagent work returns to its original parent; cancelled work stays cancelled.  
- Gateway state survives sleep or backward clock changes when locks are verified.

**Memory**  
- Unicode normalization: search matches accented and Korean words across composed/decomposed spellings; equivalent Korean/Japanese spellings no longer crowd out distinct memories.  
- Keyword search stays available during local embedding failures.  
- Corrected embedding-provider settings apply without a Gateway restart or index rebuild.  
- Memory indexing uses the configured embedding endpoint, not a chat-only subscription endpoint (was silently routing wrong).  
- Compaction resilience: summaries get more time, timeouts keep recent context, estimates include tool definitions.  
- Cron-generated sessions identified correctly even when parent links form a cycle.

**Skills / Tools / Hooks**  
- Turns stop with recovery guidance after three identical consecutive tool errors.  
- Malformed file-edit requests get a JSON correction before edits run.  
- Background commands that redirect output to a file report results when they finish.  
- Commands containing NUL bytes rejected before helpers start.

**Security**  
- Sharing requests recheck permissions and conversation identity before returning a public link.  
- Subagent recovery uses the recorded child owner so same-named sessions belonging to other agents are preserved.

### 2026.10.10-beta Notable Additions

- **apply_patch atomicity (beta.2):** multi-file patch is rejected before any file changes if a later target is missing or context does not match — all-or-nothing application.  
- **before_tool_call hooks in agent exec (beta.2):** plugin `before_tool_call` hooks now fire in standalone `openclaw agent exec` sessions, closing the gap where hooks were skipped outside the main runtime.  
- **Cold-start memory fix (beta.3):** Gateway restarts no longer eagerly open every memory index; indexes loaded on first access instead.  
- **Concurrent agent init guard (beta.3):** two agents can no longer race to claim the same database on parallel initialization.

---

## What's Notable (3–5 patterns)

### 1. Tool-error loop guard
After three identical consecutive tool errors, the runtime stops the turn and surfaces recovery guidance instead of looping indefinitely. Simple to implement, high practical value — prevents agents from burning token budget on a stuck tool.

### 2. before_tool_call hooks in standalone exec sessions
Hooks that fire before every tool call now run inside standalone `agent exec` sessions, not only inside the full Control UI / main runtime. This means the hook contract is enforced regardless of how an agent is invoked — closing a class of security and observability gaps.

### 3. Cron session cycle detection
Cron-generated sessions are identified correctly even when parent-session links form a cycle. OpenClaw stores a parent chain and now detects cycles rather than following them forever.

### 4. Restart-safe reply resume
Interrupted replies (mid-turn) resume after a Gateway restart, with subagent work returning to its original parent and cancelled work staying cancelled. This requires the runtime to checkpoint turn state and a resume path in the gateway.

### 5. Memory indexing endpoint separation
Memory indexing was silently routing to the chat-subscription endpoint instead of the configured embedding endpoint. The fix separates the two and makes the embedding endpoint explicit. Subtle misconfiguration that silently degrades memory quality.

---

## What We Can Use in Lexicon

Ranked by value × effort. All file paths verified against the actual repo.

### 🔴 1. Tool-error loop guard — HIGH value / LOW effort
**Pattern:** Count consecutive identical tool errors per turn; at three, stop and emit recovery text.  
**Lexicon file:** `src/engine/runner.py`  
The `AgentRunner.handle_run()` path executes tool calls without a consecutive-error counter. Adding one is ~15 lines: a counter that resets on any non-error output, increments on error, and raises a `ToolLoopError` at 3 with a user-facing message.

### 🔴 2. before_tool_call hooks in isolated/cron sessions — HIGH value / MEDIUM effort
**Pattern:** Ensure hook registry fires `before_tool_call` in all invocation paths, not just the main runtime.  
**Lexicon files:** `src/engine/hooks/registry.py` · `src/engine/hooks/loader.py` · `src/engine/runtime.py`  
If Lexicon's hooks only fire when the full `AgentRuntime` is running (e.g., not in standalone cron-triggered sessions via `src/cron/scheduler.py`), hook-enforced invariants are silently bypassed. Worth auditing the cron → runner → runtime call path to confirm hooks are wired end-to-end.

### 🟡 3. Cron session cycle detection — MEDIUM value / LOW effort
**Pattern:** Detect cycles in the parent-session chain before enqueuing cron-triggered agent runs.  
**Lexicon file:** `src/cron/scheduler.py`  
`CronScheduler._execute_job()` enqueues to a `CommandQueue`. If the parent-session link from a cron job points back to itself or through a chain that loops, the session resolution could recurse. Add a visited-set walk up the parent chain before enqueue.

### 🟡 4. Memory compaction resilience — MEDIUM value / MEDIUM effort
**Pattern:** Give compaction a hard timeout; on timeout, keep the most recent context rather than dropping everything. Instrument why compaction timed out.  
**Lexicon file:** `src/engine/context/compactor.py`  
Current compaction may have no timeout, meaning a slow LLM call during compaction could stall the turn indefinitely. Wrapping the compaction call in `asyncio.wait_for` with a fallback to tail-preserve behavior is a low-risk resilience win.

### 🟢 5. Memory indexing endpoint separation — MEDIUM value / LOW effort
**Pattern:** Assert that the embedding endpoint used for memory indexing is the one from `embed_model` config, not the chat endpoint.  
**Lexicon files:** `src/engine/memory/manager.py` · `src/engine/memory/search.py`  
If `MemoryManager` pulls the LLM provider from a shared `LLMRouter` without specifying the embedding endpoint, it may silently use the chat model. Adding an explicit `embed_provider` kwarg and a startup assertion would catch this.

---

## My Picks — What to Spike Next

1. **Tool-error loop guard** (`src/engine/runner.py`): Highest ROI. Pure addition, no architecture change, directly prevents a class of runaway agent sessions. Spike: add consecutive-error counter to `AgentRunner.handle_run()`, emit `ToolLoopError` at threshold 3, write a unit test.

2. **before_tool_call hooks audit** (`src/engine/hooks/registry.py`): Second priority. Hooks that don't fire are invisible — they give false confidence. Spike: trace the cron → scheduler → runner → runtime path and confirm `HookRegistry.run_before_tool_call()` is called. If not, wire it in `AgentRunner.handle_run()` before the tool dispatch.
