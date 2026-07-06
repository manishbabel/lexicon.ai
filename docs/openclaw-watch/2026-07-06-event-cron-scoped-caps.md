# OpenClaw Watch — 2026-07-06: Event-Driven Cron & Scoped Capability Profiles

**Baseline:** 2026.5.27 stable / 2026.5.28-beta.2 beta  
**This digest covers:** 2026.6.11 stable · 2026.7.1-beta.1 · 2026.7.1-beta.2 beta

---

## What Shipped

### 2026.6.11 · Stable · June 30, 2026

Reliability release. Headline: "fixes for misplaced replies, stuck sends, reconnects, model setup
failures, and safer admin defaults."

- Channel delivery reliability across Telegram, WhatsApp, Matrix, Google Chat, iMessage, Feishu,
  Mattermost, WebChat, terminal UI, and Control UI
- Memory-wiki transient retry: retries path-mismatch errors during simultaneous page rewrites while
  still aborting unsafe or persistent filesystem writes
- Heartbeat/health-check reply shielding: reasoning-capable models now return the assistant's
  intended reply from heartbeat checks, not raw internal reasoning traces
- CLI help command performance: `--help` now responds in tens of milliseconds (was 1.6–1.8 s)
- Nightly dreaming jobs no longer trigger unnecessary recall work against the 45-second timeout

**⚠ Caution — known regressions in this version:**
- Tool output goes empty after the first call (missing reentrancy guard in tool dispatch)
- `memory_search` race condition corrupts indices under concurrent writes
- Packaging flaw omits a reentrancy guard

The patterns from this release are worth porting, but verify against the beta cycle's fixes before
wiring anything into production Lexicon code.

---

### 2026.7.1-beta.1 · Beta · July 2, 2026

First drop for the 2026.7.1 cycle. All the architectural work from this cycle lives here.

- **Event-driven cron** — new `on-exit` schedule kind: wakes an agent when a watched command exits;
  session-targeted runs can also detach cleanly after completion
- **External harness attachment** — `openclaw attach` launches an external harness against an
  already-running Gateway session, decoupling harness lifetime from session lifetime
- **Telegram Codex workflows** — `/login` pairing, active Codex run steering, final-reply recovery
  across transient API failures (channel-specific, not architectural)
- **Scoped capability profiles** — per-conversation tool and access boundaries; each session can
  restrict which tools and capabilities the agent can reach
- GPT-5.6 model catalog support (dep bump, no architecture change)
- iOS 26 visual refresh, iMessage native polls (native app, not applicable)

### 2026.7.1-beta.2 · Beta · July 5, 2026

Incremental polish on beta.1; no new architectural primitives.

- Session-first sidebar, compact context meter in Control UI
- Mac local Gateway auto-setup on first launch
- Warm light theme

---

## What's Notable

### 1. Event-Driven Cron (`on-exit` schedule kind)
OpenClaw extends its scheduler from "time-based" (interval, cron expression, one-shot datetime) to
"event-triggered": a new `on-exit` kind fires an agent when a watched external command exits.
Session-targeted runs gain a detach mode so they can outlive the triggering event cleanly. This
decouples scheduling from the clock — useful for "run agent after ingestion finishes" without
polling.

### 2. Scoped Capability Profiles per Conversation
Each conversation session can carry a capability profile that limits which tools and skills are
available to the agent for that session. This is a security isolation primitive: instead of one
global allowlist for a persona, each conversation gets its own filtered view of the tool registry.

### 3. External Harness Attachment
`openclaw attach` lets an external process attach a new harness to an existing Gateway session
without restarting it. The Gateway session is the long-lived owner; the harness is a replaceable
client. Enables interactive and debugging workflows without session teardown.

### 4. Memory Write Retry with Unsafe-Write Guard
Memory writes now have two-tier error handling: retry transient path mismatches (concurrent page
rewrites), hard-stop on unsafe or persistent filesystem writes. The same code path handles both
instead of treating every error as fatal.

### 5. Heartbeat Reply Shielding
Reasoning-capable models produce internal trace content before their final reply. OpenClaw now
filters this at the heartbeat/health-check boundary: callers see only the final assistant reply, not
the reasoning trace. Important for any path where scheduled or health-check output is logged,
surfaced to users, or sent across a channel.

---

## What We Can Use in Lexicon

Ranked by value-to-effort ratio — highest ratio first.

### A. Memory Write Retry with Unsafe-Write Guard
**Value: Medium · Effort: Low**  
**File:** `src/engine/memory/manager.py`

`MemoryManager` calls into four memory layers (working, short-term, episodic, QMD vault). Writes to
JSONL stores (`src/engine/memory/short_term.py`, `src/engine/memory/episodic.py`) can encounter
transient `FileNotFoundError` or path-lock errors under concurrent writes. Adding a retry-on-
transient / hard-fail-on-unsafe split makes the manager resilient without masking real errors.
Targeted change, no interface changes required.

### B. Heartbeat Reply Shielding in Orchestrator
**Value: High · Effort: Low**  
**File:** `src/engine/orchestrator.py`

`Orchestrator` runs sub-agents oneshot and collects their response before returning it to the Chief.
If the sub-agent's LLM provider returns reasoning traces alongside the final reply (extended
thinking in Claude 3.x / `claude_provider.py` or `litellm_provider.py`), those traces can surface
in the orchestrator result. Apply the same shielding: strip reasoning content at the
`Orchestrator._run_subagent()` boundary, return only final `assistant` role text. Also relevant for
cron-triggered runs in `src/cron/scheduler.py` where `_execute_job()` logs agent output.

### C. Event-Driven Cron (`on-exit` trigger kind)
**Value: High · Effort: Medium**  
**Files:** `src/cron/store.py`, `src/cron/scheduler.py`, `src/cron/defaults.py`

`CronScheduleConfig` in `store.py` currently accepts `"at" | "every" | "cron"` types. Adding
`"on-exit"` as a fourth kind — with a `watch_command: str` field — gives the scheduler a way to
fire a job when an external process exits (e.g., an ingestion script, a build, a vault sync).
`CronScheduler` in `scheduler.py` would need a watcher loop alongside APScheduler. The `defaults.py`
patterns can seed a default `on-exit` job for common Lexicon pipelines. Medium effort: new schedule
kind, new watcher, APScheduler integration stays mostly unchanged.

### D. Scoped Capability Profiles per Session
**Value: High · Effort: High**  
**Files:** `src/engine/registry.py`, `src/engine/skills.py`, `src/gateway/session.py`

`AGENT_TOOL_ALLOWLIST` in `registry.py` is currently a static per-persona dict. Scoped capability
profiles would move this to a per-session structure: each `GatewaySession` in `gateway/session.py`
carries an optional capability profile that overrides or narrows the persona-level allowlist. This
threads through `AgentRegistry` → `ToolRegistry` → `SkillRegistry`. Architecturally significant;
worth a design spike before any code. Port only after C ships and usage patterns are clearer.

---

## My Picks: What to Spike Next

1. **B — Heartbeat reply shielding** in `src/engine/orchestrator.py`. Lowest effort, highest
   correctness/security value. Check whether `claude_provider.py` or `litellm_provider.py` passes
   `thinking` blocks through to the orchestrator result today — if yes, strip them at the
   orchestrator boundary before returning to Chief.

2. **A — Memory write retry** in `src/engine/memory/manager.py`. Quick targeted change. Add a
   `_write_with_retry(fn, *, max_attempts=3)` helper; call it from the short-term and episodic
   store writes. Keep the hard-fail path for any error that isn't transient path/lock related.

3. **C — Event-driven cron** in `src/cron/store.py` + `src/cron/scheduler.py`. Open a design
   ticket: what Lexicon pipelines would actually benefit from `on-exit` scheduling? That answer
   shapes the watcher implementation before any code is written.

Hold **D** until C lands. Per-session capability scoping requires changes across the session→engine
boundary; shipping event-driven cron first will surface the patterns D needs.
