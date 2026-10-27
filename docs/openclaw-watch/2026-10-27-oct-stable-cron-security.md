# OpenClaw Watch — 2026-10-27

## What shipped

| Track | Version | Date | Headline |
|---|---|---|---|
| Stable (latest) | 2026.10.8 | 27 Oct 2026 | Update recovery, cron child-session protection, bounded output, security hardening |
| Extended-stable (LTS equiv) | 2026.9.35 | 27 Oct 2026 | Worker pooling, bounded event-loop scans, stale-lock liveness, SQLite 3.54 data-safety |
| Beta | 2026.10.10-beta.4 | 27 Oct 2026 | hooks.token isolation, result-gated cron, scoped follow-up authority, human-note preservation |

Previous baseline: stable 2026.5.27 / beta 2026.5.28-beta.2 (last checked 2026-09-23).

### Key release notes excerpts

**2026.10.8 stable**
- Cron cleanup keeps live child sessions; cron jobs keep running after a hook plugin is replaced.
- Rate-limited LLM profiles cool down only as long as the provider's retry header requests.
- Killed runs release the restart-recovery fence, unblocking conversations.
- Orphaned maintenance workers no longer block CLI commands or Gateway startup.
- Long HTML/JSX answers and crafted markup no longer stall the Gateway.
- Security: sandboxed spawned children cannot run host CLI backends; secret egress proxy rejects distrusted certificate chains.

**2026.9.35 extended-stable**
- Archive workers pooled across session deletes (no spawn-per-op).
- Bounded regex/tag scans prevent event-loop stalls on large content.
- State directory created `0700` regardless of umask; credentials redacted from `mcp list/show` and logs.
- Model fallback triggers after unexecuted tool calls and during compaction.
- Stale Linux state locks recovered only when the owning process is no longer live.

**2026.10.10-beta.4**
- `hooks.token` kept out of agent exec and CLI child environments by default (per-command opt-in override).
- Cron runs wait for tool results before summarizing — no more premature "done" from an unfinished tool.
- Scheduled same-conversation follow-ups keep the operator's authority including one-shot rearming.
- Human-authored Memory Wiki notes survive concept re-import; a marked-slot distinguishes them.
- Config writes (`config set/unset/setup`) routed through the running Gateway as a single `config.patch`.

---

## What's notable

### 1. hooks.token secret isolation (beta → stable)
The hooks token is stripped from agent exec environments and CLI child processes by default. Access is explicit: a per-command override is required. This is a "fail-closed credential leakage" pattern — children inherit the least access by default, operators opt into more. Worth backporting regardless of the beta status.

### 2. Provider-driven backoff in the LLM router
When an LLM provider rate-limits, the cooldown duration comes directly from the provider's retry header, not a fixed local timer. This keeps the system in lockstep with real provider state and avoids both under-cooling (retrying too soon) and over-cooling (sitting idle when the window expired).

### 3. Result-gated cron summaries
Cron runs wait for all tool results to arrive before producing a summary. Previously a cron job could summarize before async tools resolved, producing meaningless "completed" outputs. The gate is a simple invariant: no summary until the tool result queue is empty.

### 4. Bounded content scans against event-loop stalls
Regex, tag, and HTML scanning over streaming content is capped at a per-scan limit. Without the cap, a crafted large payload stalls the event loop, which blocks all other sessions. The bound is a backpressure primitive.

### 5. Child-session protection across cron and hook plugin reloads
Cron cleanup now checks whether a child session is live before tearing it down. Hook plugin reloads no longer kill running cron jobs. This separates plugin lifecycle from session lifecycle — two orthogonal concerns that were accidentally coupled.

---

## What we can use in Lexicon

Ranked by value/effort. All file paths verified against `src/`.

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---|---|---|---|
| 1 | **Provider-driven backoff** — read retry-after from the provider response header; drive cooldown from that, not a fixed sleep | High | Low | `src/engine/llm/router.py` |
| 2 | **hooks.token isolation** — strip hook credentials from child exec environments; require explicit per-command override to pass them | High | Medium | `src/engine/hooks/loader.py`, `src/engine/hooks/registry.py` |
| 3 | **Result-gated cron summaries** — add a `pending_tools` counter to cron job state; block summary until counter reaches zero | High | Medium | `src/cron/scheduler.py` |
| 4 | **Child-session liveness check in cron cleanup** — before tearing down a session in cron cleanup, check if it has live children; skip teardown if so | Medium | Low | `src/cron/scheduler.py` |
| 5 | **Bounded content scans** — add a character limit to any regex or tag scanning over streamed/large content in the gateway | Medium | Low | `src/gateway/session.py` |

---

## My picks for what to spike next

**Spike 1 (highest ROI): Provider-driven backoff** in `src/engine/llm/router.py`
Low effort, immediately makes Lexicon's LLM routing more resilient to rate-limit bursts. The router already handles provider errors; this is an additive read of the `Retry-After` header to set cooldown duration.

**Spike 2: hooks.token isolation** in `src/engine/hooks/loader.py`
The hooks system passes credentials today — worth auditing what leaks into child envs. This is a security boundary that gets harder to retrofit later. Medium effort but important before production use of multi-agent flows.
