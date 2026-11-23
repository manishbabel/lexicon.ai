# OpenClaw Watch — 2026-11-23: Aug–Nov Surge

> **Coverage:** 2026.6.1 through 2026.11.7 (stable) and 2026.11.10-beta.1 (beta)
> **Previous baseline:** 2026.5.27 stable / 2026.5.28-beta.2 beta (last verified 2026-09-23; prior run could not reach GitHub)
> **New latest stable:** 2026.11.7 (released 2026-11-23, marked Latest)
> **New latest beta:** 2026.11.10-beta.1 (released 2026-11-19)

---

## What Shipped

### 2026.8.1 — "OpenClaw 2.0" (released 2026-08-31)

The largest release in the project's history. Breaking changes (OpenProse removal, OpenAI route migration), major new subsystems across every layer.

**Headline changes:**
- Default agent concurrency scales with CPU count (8–16); session permission modes anchored to workspace/worktree
- Conversation branching: fork from any persisted user message, switch between retained transcript branches
- **Grounded dreaming**: model-backed background memory consolidation promotes provenance-qualified material to long-term memory; logged in Dream Diary
- **Self-learning skills**: reusable lessons captured automatically; scanner-approved skills applied without prompts; Skill Workshop for review/consolidation
- **Approve-once for recurring automations**: permission granted for an exact operation on a cron job; inspectable and revokable
- **A2A 1.0 agent channel** (opt-in): direct agent-to-agent messaging channel
- **IMAP email trigger**: email-driven agent invocations
- Heartbeat ambient alerts route to resolvable owner DM by default
- Recovery: interrupted one-shot jobs resume after restart; cron delivery text kept as bounded context
- Private credential requests (masked prompt, out of model context); team-scoped secrets in SQLite

### 2026.10.33 — Extended-stable / LTS (released 2026-11-18)

Gateway-only LTS build. No native apps.

**Headline changes:**
- Bounded memory use for large conversation histories
- Recovery from dead update executors
- **Session import from Claude Code and Codex transcripts**

### 2026.11.6 (released 2026-11-19) and 2026.11.3–2026.11.5

Stable patch train. 406 commits, 157 contributors across the 2026.11.6 cycle.

### 2026.11.7 — Current latest stable (released 2026-11-23)

**Headline changes:**
- **Interrupted reply and subagent result recovery across Gateway restarts**
- Smoother Git/package updates and better Gateway responsiveness
- ChatGPT model discovery
- Breaking SDK changes: session control, gateway methods, start-deadline field

### 2026.11.10-beta.1 (released 2026-11-19)

**Headline changes:**
- **Agent templates** installable from ClawHub packages
- OpenClaw ID node connections; browser handoff
- **Copy-and-swap state upgrades** at startup
- Chat steering and queue editing

---

## What's Notable (5 Patterns)

### 1. Self-learning skills with scanner gating (2026.8.1)
OpenClaw captures strong lessons in the background and auto-applies scanner-approved skills without approval prompts. A `skills.workshop.approvalPolicy: "pending"` flag restores the gate. The Skill Workshop consolidates learned collections through a recoverable review flow with `/learn` reuse.

**Why it matters:** Autonomous skill growth with a safety gate is a reusable pattern for any agent that runs routines—learned behavior accumulates without developer intervention, and the gate prevents runaway self-modification.

### 2. Grounded memory consolidation ("dreaming") (2026.8.1)
A background job runs model-backed consolidation: provenance-qualified material is promoted to long-term memory and logged. Owners can audit source sessions, exclude sources, and use `openclaw memory forget` to remove derived memory without touching source transcripts.

**Why it matters:** Episodic-to-long-term promotion with provenance tracking is a principled memory architecture that prevents hallucinated recall and supports auditability.

### 3. Approve-once for recurring automations (2026.8.1)
Cron jobs can be granted permission for an exact operation. Permissions are inspectable and revokable per job; any change to the job or operation requires fresh approval.

**Why it matters:** Lexicon's cron runs privileged tools on a schedule with no per-operation consent layer. This pattern closes that gap cheaply—it's additive and self-contained.

### 4. Interrupted reply/subagent recovery across restarts (2026.11.7)
When a Gateway restarts mid-reply or mid-subagent, interrupted results are recovered and replayed to the original requester. The fix does not require the caller to retry.

**Why it matters:** Lexicon's orchestrator and runner have no crash-recovery path for in-flight tool calls. This pattern—checkpoint + replay on restart—would meaningfully raise reliability.

### 5. Copy-and-swap state upgrades (2026.11.10-beta.1)
Schema migrations are applied by writing a new state copy and swapping atomically at startup, rather than upgrading in place.

**Why it matters:** In-place migrations on the cron store or memory index can corrupt state if the process dies mid-migration. Copy-and-swap makes upgrades safe on any filesystem.

---

## What We Can Use in Lexicon

Ranked by value/effort ratio (high value first, then lower effort):

| # | Pattern | Value | Effort | Lexicon target |
|---|---------|-------|--------|----------------|
| 1 | Approve-once for cron operations | High | Low | `src/cron/scheduler.py`, `src/cron/store.py` |
| 2 | Interrupted reply/subagent recovery | High | Medium | `src/engine/runner.py`, `src/engine/orchestrator.py` |
| 3 | Grounded memory consolidation | High | Medium | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py` |
| 4 | Self-learning skills (scanner gating) | High | High | `src/engine/skills.py` |
| 5 | A2A agent channel | Medium | Medium | `src/gateway/router.py`, `src/engine/tools/route_to_agent.py` |
| 6 | Session import from external transcripts | Medium | Medium | `src/gateway/session.py` |
| 7 | Copy-and-swap state upgrades | Medium | Low | `src/cron/store.py`, `src/engine/memory/manager.py` |

**Notes:**
- `src/cron/scheduler.py` and `src/cron/store.py` exist and are the natural home for approve-once and copy-and-swap.
- `src/engine/runner.py` + `src/engine/orchestrator.py` cover the runtime restart-recovery gap.
- `src/engine/memory/manager.py` + `src/engine/memory/episodic.py` are the right targets for grounded consolidation; `src/engine/memory/transcript_index.py` already has the indexing primitives.
- `src/engine/tools/route_to_agent.py` is a live stub for agent routing; A2A would extend it.

---

## Picks — What to Spike Next

**Spike 1 (this week): Approve-once for cron operations → `src/cron/scheduler.py`**
Most self-contained. Lexicon cron jobs run tools with no per-operation consent layer. Adding an `approved_operations` field to the cron store and a check in the scheduler before each tool dispatch is a small, safe, high-signal change.

**Spike 2 (next sprint): Grounded memory consolidation → `src/engine/memory/manager.py`**
The transcript index (`src/engine/memory/transcript_index.py`) and episodic store (`src/engine/memory/episodic.py`) are the right substrate. A background consolidation task that promotes high-confidence episodic items to long-term memory—with provenance tags—would meaningfully improve multi-session recall.

---

*Sources: [github.com/openclaw/openclaw/releases](https://github.com/openclaw/openclaw/releases), [/releases/tag/v2026.8.1](https://github.com/openclaw/openclaw/releases/tag/v2026.8.1)*
