# OpenClaw Watch — 2026-08-31

## What shipped

| Version | Date | Type | Headline |
|---------|------|------|----------|
| **2026.8.1** | 2026-08-31 | Stable | Background memory consolidation, private credential requests, scoped automation approvals, batched tool discovery, gateway external supervision |
| **2026.7.1** | 2026-07-01 | Stable | Gateway crash-loop prevention with stable repair path; model/provider expansion; wake-on-change scheduling |
| **2026.9.1-beta.1** | 2026-08-28 | Beta | Gateway restart recovery preserving admitted turns across checkpoints; worker re-armed admission-deadline launches |

Baseline was 2026.5.27 (stable) / 2026.5.28-beta.2 (beta).

---

## What's notable

### 1. Background memory consolidation ("grounded dreaming") — 2026.8.1

A model-backed background pass runs periodically over episodic memory: merging near-duplicate entries, surfacing recurring themes, expiring stale facts. It records a Dream Diary (audit log of what was merged/dropped) and can be disabled per-agent. This is the first OpenClaw release to treat memory not as a passive store but as something that actively maintains itself.

### 2. Scoped, revocable permission grants for recurring work — 2026.8.1

"Approve recurring work once" issues a permission receipt scoped to the exact operation set (tool name + args pattern). Grants are inspectable and individually revocable without disrupting sibling automations. This is architecturally distinct from simple on/off flags: each receipt has a scope, issuer, and expiry.

### 3. Private credential requests — 2026.8.1

Tool calls can declare credential parameters as `SecretRef`. Values are prompted via a masked UI widget, never written into the model context or transcript. An opt-in proxy layer further limits substitution to pre-approved destination domains, so credentials can't leak through a rogue tool endpoint.

### 4. Gateway crash-loop prevention — 2026.7.1

Gateways that fail repeatedly within a time window no longer restart indefinitely. Instead they transition to a stable repair state (a read-only diagnostic shell) from which a human or supervisor process can inspect logs and apply safe migrations. This prevents resource exhaustion and makes failure modes observable.

### 5. Batched tool discovery — 2026.8.1

`tool_search` now accepts a list of intent strings and returns capability matches across all of them in one call, deduplicating overlapping tool results. This replaces the loop of sequential single-intent lookups that accumulated latency.

---

## What we can use in Lexicon

Ranked by value/effort (high value first):

| # | Pattern | Value | Effort | Lexicon files |
|---|---------|-------|--------|---------------|
| 1 | **Private credential masking in tool dispatch** | High | Low | `src/engine/tools/registry.py`, `src/shared/config.py` |
| 2 | **Background memory consolidation pass** | High | Medium | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py`, `src/cron/scheduler.py` |
| 3 | **Scoped, revocable permission receipts for cron/hooks** | High | Medium | `src/engine/hooks/registry.py`, `src/cron/scheduler.py` |
| 4 | **Gateway crash-loop circuit breaker** | Medium | Low | `src/gateway/server.py` |
| 5 | **Batched capability lookup in tool registry** | Medium | Low | `src/engine/tools/registry.py` |

### Detail

**1 — Private credential masking** (`src/engine/tools/registry.py`, `src/shared/config.py`):  
Mark tool parameter schemas with a `secret: true` annotation. The tool dispatcher in `registry.py` strips or masks values before they reach the LLM context (model sees `<secret:name>` placeholder). Config values in `config.py` marked sensitive get the same treatment. Low-risk, high-security-payoff first spike.

**2 — Background memory consolidation** (`src/engine/memory/manager.py`, `src/engine/memory/episodic.py`, `src/cron/scheduler.py`):  
Add a `consolidate()` method to `manager.py` that calls the LLM against a window of recent episodic entries to produce merge/expire decisions. Schedule it from `src/cron/scheduler.py` on a low-frequency cron (e.g., nightly). Write a consolidation log entry per run alongside the existing memory entries in `episodic.py`.

**3 — Scoped permission receipts** (`src/engine/hooks/registry.py`, `src/cron/scheduler.py`):  
Replace the current boolean auto-approve flags with a `PermissionReceipt(tool, arg_pattern, scope, expires_at)` structure stored in `hooks/registry.py`. `scheduler.py` checks receipts before invoking a recurring job. Receipts are queryable and individually revocable without touching scheduler state.

**4 — Gateway circuit breaker** (`src/gateway/server.py`):  
Track restart timestamps in a rolling window. If `restart_count > N within T seconds`, stop the restart loop and enter a `REPAIRING` state that serves a minimal diagnostic endpoint. Avoids the current all-or-nothing crash behavior.

**5 — Batched tool lookup** (`src/engine/tools/registry.py`):  
Accept `list[str]` in the registry's search method, run all intent matches in one pass over the tool index, deduplicate, return combined results. Reduces latency for agents that probe multiple capability categories before selecting a tool.

---

## My picks for what to spike next

**Spike 1 (this week): Private credential masking** — one-day change to `src/engine/tools/registry.py` + `src/shared/config.py`. Immediate security benefit with no architectural risk. Adds `secret` flag to tool schema, strips value before LLM dispatch.

**Spike 2 (next sprint): Background memory consolidation** — extends the existing `manager.py` / `episodic.py` / `scheduler.py` stack with a consolidation pass. Directly improves long-running agent quality and gives us an audit log of memory decisions.
