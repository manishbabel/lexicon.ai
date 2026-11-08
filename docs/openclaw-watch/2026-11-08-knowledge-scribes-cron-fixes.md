# OpenClaw Watch — 2026-11-08

**Coverage:** 2026-09-23 (last check) → 2026-11-08 (today)
**Sources:** github.com/openclaw/openclaw/releases (primary)

---

## What shipped

### Stable releases

| Version | Date | Headline |
|---------|------|----------|
| **2026.11.1** _(Latest)_ | 05 Nov 2026 | Channel reliability, subagent continuity, provider rate-limit recovery, credential redaction, Mac settings hardening |
| **2026.10.10** | 03 Nov 2026 | Full notes not captured; preceded by beta.5 below |
| 2026.10.9, 2026.9.36, 2026.10.8, 2026.9.35, 2026.10.7 | Oct–Nov 2026 | Point releases (notes not captured from primary source) |
| **2026.9.5** | Sep 2026 | Atomic updates, plugin hot-reload without gateway restart, credential masking in tool output |
| **2026.9.4** | Sep 2026 | Interactive terminal questions |
| **2026.8.1 ("OpenClaw 2.0")** | 30 Aug 2026 | Major: redesigned UI, faster setup, shared cloud sessions, browser app updates |

### Beta releases

| Version | Date | Headline |
|---------|------|----------|
| **2026.11.5-beta.1** _(Latest beta)_ | 04 Nov 2026 | Knowledge Scribes, PostgreSQL data plane, Control UI overhaul, PR-from-chat, cross-device execution, decision routing |
| 2026.10.10-beta.5 | 30 Oct 2026 | Node >=24.16.0 compat, gateway stream hardening, cron missed-slot guard, tighter exec allowlist |
| 2026.10.10-beta.4 | ~Oct 2026 | Gateway config hot-apply, Memory Wiki human-note preservation, `hooks.token` env isolation |

---

## What's notable

### 1. Knowledge Scribes (2026.11.5-beta.1)
First-class reusable knowledge-capture workflows layered over memory. The key architectural move: separates the _capture act_ from storage, enabling structured extraction pipelines that can be parameterized and reused across sessions. Memory becomes a typed artifact, not a side-effect of conversation.

### 2. Cron missed-slot guard (2026.10.10-beta.5)
> "Missed slots with stale next-run times are no longer dropped."

On scheduler wake, OpenClaw now distinguishes _not-yet-fired_ from _overdue_: if `now > next_run + grace`, the slot fires immediately rather than being skipped. Prevents silent cron gaps after gateway restarts or container pauses.

### 3. Provider rate-limit awareness (2026.11.1)
> "Recovery respects provider rate-limit timing."

LLM provider 429 responses carry `Retry-After` or `x-ratelimit-reset-requests`. OpenClaw now honors those signals instead of retrying on a fixed backoff, eliminating retry storms when quotas are hit.

### 4. Gateway stream hardening (2026.10.10-beta.5)
> "Replies containing tool-call-like XML or ending in partial HTML tags no longer stall the Gateway."

A buffering state machine at the stream boundary detects partial closes (open XML/HTML tag at chunk boundary) and holds the buffer until a safe flush point. Prevents hung streaming responses.

### 5. Credential redaction before model call (2026.9.5 → 2026.11.1)
Registered secrets are masked in tool output _before_ the next LLM context window is built, not just at display time. Defense-in-depth: secrets never enter the prompt. Iterated across two releases — 2026.9.5 introduced it, 2026.11.1 broadened the redaction surface.

---

## What we can use in Lexicon

> All file paths verified present in `src/`.

| Rank | Pattern | Value | Effort | Lexicon target |
|------|---------|-------|--------|----------------|
| 1 | **Cron missed-slot guard** | High | Low | `src/cron/scheduler.py`, `src/cron/store.py` |
| 2 | **Provider rate-limit Retry-After** | High | Low | `src/engine/llm/router.py`, `src/engine/llm/provider.py` |
| 3 | **Gateway XML/partial-tag stream hardening** | Medium | Medium | `src/gateway/server.py`, `src/gateway/router.py` |
| 4 | **Credential redaction before context window** | High | Medium | `src/engine/tools/registry.py` |
| 5 | **Knowledge Scribes memory pipeline** | High | High | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py`, `src/engine/skills.py` |

---

## My picks for what to spike next

### Spike 1 — Cron missed-slot guard (`src/cron/scheduler.py`)

**Highest value-to-effort ratio.** Lexicon's scheduler keeps next-run timestamps in `src/cron/store.py`. The fix is minimal: on job pickup, compare `now` against `stored_next_run + grace_period`; if overdue, fire immediately and log the missed slot instead of advancing to the next scheduled time. Prevents silent gaps after container restarts — which Lexicon is especially exposed to as a cloud-deployed service.

**Sketch:**
```python
# src/cron/scheduler.py — on job pickup
MISSED_SLOT_GRACE = timedelta(seconds=30)
if now > stored_next_run + MISSED_SLOT_GRACE:
    logger.warning("cron: missed slot for %s, firing late", job_id)
    fire_job(job)
```

### Spike 2 — Provider rate-limit Retry-After (`src/engine/llm/router.py`)

Lexicon's router likely retries on a fixed backoff today. Reading `Retry-After` from 429 responses (or `x-ratelimit-reset-requests` for Anthropic/OpenAI) would prevent retry storms when LLM quotas are hit. Low risk, high reliability gain. `src/engine/llm/claude_provider.py` and `src/engine/llm/openai_provider.py` are the right insertion points; `src/engine/llm/router.py` orchestrates retry logic.
