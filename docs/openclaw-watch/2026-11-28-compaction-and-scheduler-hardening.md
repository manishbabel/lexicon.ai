# OpenClaw Watch — 2026-11-28

**Stable:** 2026.11.10 (25 Nov 2026)  
**Beta:** 2026.12.1-beta.1 (28 Nov 2026)  
**Previous baseline:** 2026.5.27 / 2026.5.28-beta.2 (last checked 2026-09-23)

---

## What shipped

### 2026.12.1-beta.1 (28 Nov — beta)
- Automatic context compaction triggers at **85% of the context window**; cache routes are reused across compactions.
- Scheduler automations **back off when a provider pushes back** and can run up to eight overflow runs when memory permits.
- Trusted-proxy auth adds **opt-in Cloudflare Access JWT verification** beyond forwarded identity headers.
- Lean Gateways share core worker code within one host and admit additional workers only within a **memory budget**.
- Authorized shared sessions open in their source Control UI over outbound WSS (Session Share).
- Subagent undelivered child completions settle into parent history; duplicate final replies are suppressed.
- Credential limits on assistant media URLs; hidden shell-startup env assignments rejected.
- Slack shows streamed reasoning as task rows; Teams and Feishu channel delivery fixes.

### 2026.11.10 (25 Nov — stable, Latest)
- Large stable rollup: 8 309 commits, 349 contributors. Detailed changelog at `docs.openclaw.ai/releases/2026.11.10`.

### 2026.10.34 (26 Nov — extended-stable patch on the 2026.10.x line)
- Compaction now runs **before predicted context overflow**, not after the provider has cached tool results you'd cut.
- New channel tokens saved through the **secret store, not written to config as plaintext**.
- Independent channel requests (e.g. Discord DMs) are **queued rather than replacing an active task**.
- Claude CLI final answers preserved after progress messages; long turns no longer repeat tool work on a fallback model.
- PostgreSQL: silent connection loss recovery; large maintenance ops can finish without timeout.
- GPT-6.2 Astra / Sol model selection on OpenAI and ClawRouter routes.

---

## What's notable (patterns worth porting)

### 1. Predictive context compaction (two-part pattern)
OpenClaw now compacts at a threshold (85%) *before* the window is full, and targets the compaction to avoid cutting content the provider already has cached. These are two separate improvements that compose: a **threshold trigger** in the token-counter path, and a **cache-aware pruning strategy** that prunes uncached content first. This avoids the classic failure mode where compaction discards tool results the provider cached on a prior turn, inflating costs and corrupting context.

### 2. Provider-backpressure-aware scheduler
Automations detect provider-side rate limiting (`429` / backoff signals) and self-throttle while queuing up to eight deferred runs in memory. This turns a hard failure into graceful degradation: scheduled tasks don't drop silently when the LLM provider is under load.

### 3. Trusted-proxy JWT verification (Cloudflare Access)
Beyond trusting `X-Forwarded-For` / identity headers, the gateway now optionally validates a Cloudflare Access JWT from the `Cf-Access-Jwt-Assertion` header, binding each session to a verified identity. Prevents header-spoofing attacks when deploying behind Cloudflare Access.

### 4. Secret-store enforcement for channel credentials
Moving channel tokens from plaintext config to the secrets layer is an infrastructure hygiene win: secrets rotate without config redeployments, and tokens are never written to disk as plain text. The fix is narrow but the pattern applies to any credential Lexicon currently stores in `shared/config.py`.

### 5. Per-request queuing in channel adapters
Instead of cancelling an in-flight task when a new channel message arrives, enqueue the new request and serve it after the active run completes. This eliminates interleaved replies and lost responses when users send rapid follow-ups.

---

## What we can use in Lexicon

> All file paths verified present in `src/`.

| # | Pattern | Value | Effort | File(s) |
|---|---------|-------|--------|---------|
| 1 | **Threshold-based proactive compaction** — trigger `src/engine/context/compactor.py` at 85% of model context limit, not at 100% | High | Low | `src/engine/context/compactor.py`, `src/engine/context/token_counter.py` |
| 2 | **Cache-aware pruning** — in `pruner.py`, prune uncached turns first; leave content already in the provider's cache | High | Medium | `src/engine/context/pruner.py`, `src/engine/context/compactor.py` |
| 3 | **Scheduler backoff + deferred run queue** — catch provider 429s in `scheduler.py` and re-enqueue, capped at N overflow slots | Medium | Medium | `src/cron/scheduler.py`, `src/cron/store.py` |
| 4 | **Secrets store for config credentials** — move any plaintext token/key in `shared/config.py` to a secret-store read | Medium | Low | `src/shared/config.py` |
| 5 | **Request queuing in gateway session** — enqueue incoming messages when a run is active rather than superseding it | Medium | Medium | `src/engine/queue.py`, `src/gateway/session.py` |
| 6 | **Cloudflare Access JWT verification** — opt-in validation of `Cf-Access-Jwt-Assertion` in `protocol.py` | Low | Low | `src/gateway/protocol.py`, `src/gateway/server.py` |

---

## My picks for what to spike next

**Spike 1 (this week): Threshold-based compaction + cache-aware pruning (items 1 & 2)**  
`src/engine/context/compactor.py` and `src/engine/context/pruner.py` already exist — the work is adding a `COMPACT_AT_FRACTION = 0.85` check to the token-counter path and teaching the pruner to rank cached turns as lower-priority removal candidates. These two changes together replicate the full OpenClaw pattern. Low risk, measurable improvement in context stability for long Lexicon sessions.

**Spike 2 (next sprint): Scheduler backoff (item 3)**  
`src/cron/scheduler.py` currently has no retry/backpressure logic based on evidence in the codebase. A bounded retry queue with exponential backoff on 429 responses would prevent silent cron-job drops under LLM load.

**Skip for now: Cloudflare Access JWT (item 6)**  
Only relevant if Lexicon is deployed behind Cloudflare Access. File the pattern for when that deployment decision is made.
