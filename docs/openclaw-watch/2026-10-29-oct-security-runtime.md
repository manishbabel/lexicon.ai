# OpenClaw Watch: 2026-10-29

**Digest period:** 2026-05-27 (prior stable baseline) → 2026-10-29  
**New stable:** 2026.10.8 (was 2026.5.27)  
**New beta:** 2026.10.10-beta.4 (was 2026.5.28-beta.2)  
**Sources:** [GitHub releases](https://github.com/openclaw/openclaw/releases) · [releases.sh](https://releases.sh/openclaw/releases)

---

## What shipped

| Version | Date | Headline |
|---|---|---|
| 2026.7.1 | Jul 13 | Control UI overhaul; session pinning/grouping; GPT-5.6, Tencent Hy3, Meta Muse Spark 1.1 support; `utilityModel` routing for lightweight tasks |
| 2026.8.1 (2.0) | Aug 30 | **Major.** Shared/cloud sessions; SQLite replaces flat transcripts; QMD memory retired (built-in Memory owns recall); write-only credential store scoped to teams; network egress declared per-host; safe Doctor config migrations at Gateway startup |
| 2026.9.3 | Sep | Skill Workshop GA: persistent agent-owned skill collections across workspaces; Doctor migrates legacy skills |
| 2026.9.4 | Sep | Conversation-to-skill: extract reusable skills from past chats |
| 2026.9.34 | Oct 24 | Atomic patching: `apply_patch` preflights full envelope before mutating workspace; `before_tool_call` plugin hooks under agent exec |
| 2026.10.5 | Oct | Skill Workshop version history + Undo |
| 2026.10.6 | Oct 22 | Durable delivery: queued turns, watched-child results, and dead-lettered deliveries survive restarts without duplication; SQLite transaction correctness |
| 2026.10.7 | Oct 24 | Last-known-good config snapshot on partial writes; interrupted package updates resume safely |
| **2026.10.8** | **Oct 27** | **Current stable.** Hook tokens kept out of child exec environments; `test -v` operand expansion requires approval; generic-node invoke refuses browser-proxy commands; sandboxed children cannot run host CLI backends; concurrent session-memory captures no longer overwrite each other; channel fixes (Slack, Matrix, Zalo, iMessage, Feishu) |
| 2026.10.10-beta.4 | Oct 27 | Scheduled follow-ups retain operator authority within the originating conversation; webhook scripts keep each webhook's automation scope; cron summaries wait for tool results; Memory Wiki preserves human-written notes on re-import; Codex subagents resume correctly after restarts |

---

## What's notable (patterns worth porting)

### 1. Hook/cron token isolation from exec environments
**2026.10.8, 2026.10.10-beta.4.** Gateway hook tokens are scrubbed before any agent exec subprocess starts. Scheduled-task authority stays scoped to the originating webhook's scope — it does not leak into child environments as ambient credentials.  
*Why it matters:* prevents privilege escalation where a cron-fired tool call could inherit hook-level access it was never granted.

### 2. Cron summarizes after tool completion
**2026.10.10-beta.4.** Cron job summaries (heartbeat digests, notifications) are deferred until all tool calls within the turn have resolved. Previously a summary could capture a still-pending tool result.  
*Why it matters:* digest accuracy; avoids phantom "no result" entries for async tools that just hadn't settled yet.

### 3. Durable queue: dead-letter + restart survival
**2026.10.6.** Queued turns and watched child results survive process restarts without duplication. Dead-lettered deliveries are persisted separately so nothing is silently dropped.  
*Why it matters:* any async delivery system loses work on crash unless messages are persisted before the ack. This is the canonical fix.

### 4. Last-known-good config snapshot
**2026.10.7.** Config writes are staged: the last-known-good snapshot is kept until the new write completes fully. A partial write leaves the prior config intact.  
*Why it matters:* trivially prevents a truncated or mid-crash config write from bricking a running service.

### 5. Concurrent session-memory write guard
**2026.10.8.** Session-memory captures that trigger simultaneously no longer clobber each other. A write guard (likely an async lock or write queue) serializes concurrent captures.  
*Why it matters:* direct parallel fix for any memory store that does read-modify-write without locking.

---

## What we can use in Lexicon

Ranked by value/effort. Only real paths under `src/` are listed.

| # | Pattern | Value | Effort | Lexicon file |
|---|---|---|---|---|
| 1 | **Hook token isolation** — scrub cron/hook credentials before spawning agent exec | High | Low | `src/engine/hooks/registry.py` · `src/cron/scheduler.py` |
| 2 | **Cron waits for tool results** — defer heartbeat summary until all tool calls settle | High | Medium | `src/cron/scheduler.py` |
| 3 | **Durable queue** — persist messages before ack; dead-letter on repeated failure | High | Medium | `src/engine/queue.py` |
| 4 | **Last-known-good config snapshot** — write to temp, swap atomically, keep prior on partial failure | Medium | Low | `src/shared/config.py` |
| 5 | **Concurrent memory write guard** — serialize concurrent session-memory captures | Medium | Low | `src/engine/memory/manager.py` |
| 6 | **Conversation-to-skill extraction** — UI/API path to promote a past exchange to a reusable skill | Medium | High | `src/engine/skills.py` |
| 7 | **Utility model routing** — route lightweight/ambient tasks through a smaller model | Low | Low | `src/engine/llm/router.py` |

---

## Spike picks

**Spike #1 (this week): hook token isolation** — `src/engine/hooks/registry.py` + `src/cron/scheduler.py`. Low effort, high security value. Audit whether `os.environ` or the exec context passed to tool subprocesses contains any hook-scoped API tokens; scrub them before the call. This is a one-session fix with no API surface change.

**Spike #2 (next): cron waits for tool results** — `src/cron/scheduler.py`. The heartbeat currently logs a summary at task completion, but async tools called inside a cron turn may not have resolved. Add a `await_tool_results()` barrier before emitting the summary. Medium effort, directly improves digest reliability.
