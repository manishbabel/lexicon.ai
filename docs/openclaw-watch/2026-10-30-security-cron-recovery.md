# OpenClaw Watch — 2026-10-30

## What Shipped

| Version | Type | Date | Headline |
|---|---|---|---|
| **2026.10.9** | stable (latest) | 2026-10-29 | Security deps, workspace tool scoping, agent + memory recovery |
| **2026.10.10-beta.5** | beta (latest) | 2026-10-30 | Cron missed-slot fix, Gateway streaming resilience, credential hardening |
| **2026.9.36** | extended-stable (gateway-only) | 2026-10-29 | LTS-equivalent: critical security + rollback fixes on late-Sep codebase |

Previous stable: 2026.5.27. Previous beta: 2026.5.28-beta.2. Last checked: 2026-09-23.

---

## What's Notable (patterns worth porting)

### 1. Workspace-scoped filesystem tools (`tools.fs.workspaceOnly`)
OpenClaw now enforces that all filesystem tools — including those dynamically built by the Gateway at runtime — are constrained to the agent's workspace directory. Delegate tools and media tools also inherit the scope. Previously, Gateway-built tools could escape workspace bounds. This closes a meaningful lateral-movement path.

### 2. Cron missed-slot recovery + startup catch-up
The scheduler no longer silently drops cron slots when the stored `next_run` timestamp is stale (e.g. after a long pause or redeploy). On restart it also runs a startup catch-up pass for any jobs that fired while the process was down. One-shot jobs finalize correctly on PostgreSQL. Forced-paused jobs are properly cancelled on explicit disable.

### 3. Gateway streaming resilience for tool-call-like XML
Streaming replies that contain tool-call-shaped XML, partial closing HTML tags, or mentions of tool calls no longer stall the Gateway or emit false "missing answer" notices. Side-question replies no longer vanish or duplicate after a tool send. This is a known class of streaming edge case that bit several Lexicon users via `src/gateway/server.py`.

### 4. Credential masking in logs and inspection surfaces
Google OAuth client secrets and MCP CLI inspection calls no longer expose live credentials. Browser pairing credentials are stripped from process arguments. This was a multi-surface hardening pass across logging, CLI child environments, and search endpoint error output.

### 5. Agent recovery after full-disk without restart
Agents self-heal when disk space is freed, without requiring a process restart. Also: transcript IDs survive idle resets, and corrupt session rows no longer crash session listings.

---

## What We Can Use in Lexicon

Ranked by value/effort. All file paths verified to exist under `src/`.

### 🔴 High value / Low effort

**A. Workspace-scoped tool enforcement**
- **What:** add a `workspace_only` flag check in the tool registry so no tool path can resolve outside the configured workspace root — even if a caller passes an absolute path.
- **File:** `src/engine/tools/registry.py` + `src/engine/workspace.py`
- **Effort:** ~1 day. Add a `is_within_workspace(path, workspace_root)` guard called before any tool that touches the filesystem. `vault_read.py` and `vault_write.py` are the immediate candidates.
- **Also touch:** `src/engine/tools/vault_read.py`, `src/engine/tools/vault_write.py`

**B. Credential masking in logger**
- **What:** add a redaction pass in `src/shared/logger.py` that scrubs known secret patterns (OAuth tokens, API keys, connection strings) before log emission.
- **File:** `src/shared/logger.py`
- **Effort:** ~half a day. Regex-based redaction on string log values, triggered at the formatter level.

### 🟡 High value / Medium effort

**C. Cron missed-slot recovery**
- **What:** when `scheduler.py` calculates `next_run` on startup, compare against current time; if the delta is negative (slot was missed), immediately enqueue a catch-up run rather than skipping to the next future slot.
- **File:** `src/cron/scheduler.py` + `src/cron/store.py`
- **Effort:** ~1–2 days. Needs a `missed_catchup_enabled` config flag and a guard for jobs where catch-up is inappropriate (e.g. one-shot digests).

**D. Gateway streaming: partial-tag stall guard**
- **What:** add a buffer flush guard in the Gateway's stream handler to detect replies that end on an unclosed XML/HTML tag and force-flush rather than stalling awaiting the closing tag.
- **File:** `src/gateway/server.py`
- **Effort:** ~1–2 days. Requires a streaming state machine inspection for unclosed `<` tokens in the buffer tail.

### 🟢 Medium value / Medium effort

**E. Agent full-disk self-healing**
- **What:** wrap `src/engine/runtime.py`'s run loop in a `DiskFullError` handler that parks the agent, polls for free space, and resumes without restart.
- **File:** `src/engine/runtime.py`
- **Effort:** ~1–2 days. Risk: polling interval needs tuning; overly aggressive polling wastes I/O.

---

## My Picks for What to Spike Next

1. **Workspace-scoped tool enforcement (A)** — closes a real attack surface in Lexicon today; `vault_write.py` has no path sanitization. Spike in `src/engine/tools/registry.py` + `src/engine/workspace.py`.
2. **Credential masking in logger (B)** — pure-additive, no behaviour change risk, immediate security win in `src/shared/logger.py`.
3. **Cron missed-slot recovery (C)** — Lexicon's scheduled digests silently miss slots after deploys; affects `src/cron/scheduler.py`.
