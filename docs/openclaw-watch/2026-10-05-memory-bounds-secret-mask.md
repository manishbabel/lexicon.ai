# OpenClaw Watch — 2026-10-05

**Stable:** 2026.9.8 (Oct 3, 2026)  
**Extended-stable (LTS):** 2026.8.35 (Oct 2, 2026)  
**Coverage:** 2026.5.28 → 2026.9.8 (first digest since baseline)

---

## What shipped

| Version | Date | Headline |
|---------|------|----------|
| 2026.8.1 | Aug 2026 | OpenClaw 2.0 — security overhaul for agent/tool/credential surface |
| 2026.9.5 | ~Sep 15 | Atomic updates; hot plugin install without gateway restart; secret masking in tool output; read-only conversation sharing |
| 2026.9.6 | Sep 23 | Regular release (macOS rebuild Sep 24) |
| 2026.9.7 | Sep 30 | Major: 518 commits / 2,818 PRs / 334 contributors — bounded reads, memory exhaustion prevention, origin validation, channel stall fixes |
| 2026.9.8 | Oct 3 | Patch on 9.7 — 58 commits / 43 PRs; heap pressure reduction, snapshot retention tuning |
| 2026.8.35 | Oct 2 | Extended-stable LTS; GPT-6.1 Sol support; 113 approved audit units |

Sources: [GitHub releases page](https://github.com/openclaw/openclaw/releases), web summary as of 2026-10-05.

---

## What's notable (5 patterns)

### 1. Secret masking in tool output (v2026.9.5)
Registered secrets are stripped from tool result strings before they reach the agent context or logs. Masking runs at the tool-execution boundary, not at the LLM layer, so it covers structured output (JSON payloads, URLs with tokens) as well as plain text.

### 2. Bounded expensive reads / memory exhaustion prevention (v2026.9.7)
`MAX_CONTEXT_CHARS` and per-source result caps are enforced as hard budgets, with explicit heap-pressure telemetry. Reads from large corpora (vector search, transcript index) are time-bounded and dropped rather than truncated mid-string, preventing partial context injection.

### 3. Hot plugin install without gateway restart (v2026.9.5)
The gateway no longer owns the plugin lifecycle; plugins register/deregister via an IPC bus while the gateway keeps serving. OpenClaw separates "plugin present in registry" from "gateway session wired to plugin," so new installs only affect new sessions.

### 4. Snapshot-based runtime recovery (v2026.9.7 / 2026.9.8)
Session state is checkpointed to disk on a configurable interval. On restart the runtime re-hydrates in-progress sessions from the latest snapshot rather than starting cold. Stale catalog hydration is bounded to prevent re-hydrating sessions older than a configurable TTL.

### 5. Origin validation on channel/webhook inputs (v2026.8.1 / 2026.9.7)
Incoming messages from all channel adapters (Discord, Slack, Telegram, IMAP, Webhooks) are validated against a per-channel origin allowlist before dispatching to the agent runtime. Failures are logged as security events, not silently dropped.

---

## What we can use in Lexicon (ranked by value/effort)

### Tier 1 — spike now

**A. Secret masking in tool output** ★★★ value / ★ effort  
→ `src/engine/tools/registry.py`  
`ToolRegistry` has no output filtering. A post-handler hook that redacts registered secret patterns (from `src/shared/config.py`) before returning tool results to the agent would close the most obvious credential-leak path. Low-risk, self-contained, testable.

**B. Hard bounds on memory recall** ★★★ value / ★★ effort  
→ `src/engine/memory/manager.py`  
`MAX_CONTEXT_CHARS = 4000` exists but the per-source caps (`QMD_SEARCH_LIMIT`, etc.) aren't enforced at the char level. QMD vector search can return large documents that saturate the budget. Add time-bounded search calls with a fallback to cached results, and enforce char budgets per source before merging.

### Tier 2 — planned sprint

**C. Origin validation for gateway inputs** ★★ value / ★★ effort  
→ `src/gateway/protocol.py`  
`parse_message()` trusts message source fields as-is. Adding an origin allowlist (configurable per channel in `src/shared/config.py`) before messages are dispatched in `src/gateway/router.py` would close an injection path if Lexicon ever gains external channel adapters.

**D. Snapshot-based session recovery** ★★ value / ★★★ effort  
→ `src/engine/runtime.py`  
No checkpoint mechanism exists today. Worth scoping as a future sprint; dependency is settling the session state shape first.

### Tier 3 — watch / defer

**E. IPC-based plugin decoupling from gateway** ★ value / ★★★★ effort  
→ `src/gateway/server.py`, `src/engine/skills.py`  
Skills already hot-reload via watchfiles (`src/engine/skills.py:1-14`). The OpenClaw pattern goes further (IPC bus), which is over-engineered for Lexicon's current scale. Revisit if Lexicon gains third-party plugin installs.

---

## My picks for what to spike next

1. **Secret masking in `ToolRegistry`** — one post-handler wrapper, closes a real gap, ships in an afternoon.
2. **Char-budget enforcement in `MemoryManager`** — QMD can already return oversized docs; bounded reads prevent context saturation as the vault grows.

Both are in `src/engine/` only, no gateway or config schema changes required.
