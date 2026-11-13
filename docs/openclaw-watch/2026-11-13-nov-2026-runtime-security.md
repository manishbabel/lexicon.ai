# OpenClaw Watch — 2026-11-13: November Runtime & Security Digest

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.11.3** | 10 Nov 2026 | Stable (latest) | Runtime correctness, credential isolation, cron resilience |
| **2026.11.5-beta.2** | 12 Nov 2026 | Beta (latest pre-release) | Paged memory history, Gateway task acceptance, security fixes |
| 2026.9.37 | 10 Nov 2026 | Extended-stable backport | Sep-line backport: safer update recovery, channel reconnect |

Previous watch baseline: stable `2026.5.27`, beta `2026.5.28-beta.2` (last checked 2026-09-23).

---

## What's Notable (5 Patterns)

### 1. Tool-failure reporting instead of silent success  *(2026.11.3)*
Unanswered tool failures are now surfaced to the caller rather than silently ending a turn as a success.  Previously an agent whose tool call went unhandled would appear to complete cleanly—masking bugs and leaving the user with wrong output.  The fix closes the gap between "turn ended" and "turn succeeded."

### 2. Credential isolation & redaction  *(2026.11.3)*
Plugin credentials, embedding keys, and child-process environment are now scoped separately; API keys are redacted from config-read traces and error surfaces (Exa errors cited by name).  This is a defence-in-depth pattern: secrets stay invisible even when debug logging is on.

### 3. Cron storage failures no longer exit the Gateway  *(2026.11.3)*
A failed write to the cron store previously brought down the Gateway process.  The fix catches the exception and continues, treating cron persistence as degraded rather than fatal.  This is the standard "partial-failure isolation" pattern for background infrastructure.

### 4. Bounded paged conversation history  *(2026.11.5-beta.2)*
Memory reads are now paged in both directions with hard bounds on archive reads.  Unbounded history loads were a silent resource hazard; bounding them makes memory access predictable under long-lived sessions.

### 5. Provider error classification: usage-limit vs rate-limit  *(2026.11.3)*
Anthropic usage-cap errors are now distinguished from rate-limit errors so they don't consume the rate-limit retry budget.  Conflating the two causes wasted retries on a condition retries can't fix.

---

## What We Can Use in Lexicon (Ranked Value / Effort)

### Pick 1 — Tool-failure reporting  `HIGH value / LOW effort`
**File:** `src/engine/runner.py`  
When a tool call result is not consumed (the LLM requests a tool, the engine dispatches it, but no handler returns a result), `runner.py` currently proceeds to the next turn.  Add a check after tool dispatch: if any requested tool has no result entry, raise or log a structured error before advancing.  This matches OpenClaw's fix and closes a silent-failure path in Lexicon's own agentic loop.

### Pick 2 — Credential redaction in config traces  `HIGH value / LOW effort`
**Files:** `src/shared/config.py`, `src/engine/skills.py`  
`config.py` exposes a `get()`/`load()` surface that returns raw config dicts.  Add a thin redact pass (regex over known key suffixes: `_key`, `_secret`, `_token`, `_password`) before any value is logged or returned to error handlers.  `skills.py` passes provider config to tool constructors—scope those values so they don't appear in `__repr__` or exception messages.

### Pick 3 — Cron storage partial-failure isolation  `MEDIUM value / LOW effort`
**File:** `src/cron/store.py`  
`store.py` persists scheduled jobs.  Wrap write operations in try/except and emit a warning log rather than re-raising; the scheduler in `src/cron/scheduler.py` should degrade gracefully when persistence is unavailable rather than propagating the exception to the Gateway.

### Pick 4 — Bounded memory archive reads  `MEDIUM value / MEDIUM effort`
**Files:** `src/engine/memory/short_term.py`, `src/engine/memory/episodic.py`, `src/engine/context/pruner.py`  
Add a `max_items` / `page_size` parameter to history-read methods and enforce it at the retrieval boundary.  The context pruner already trims tokens for LLM calls; bounding the read prevents loading unbounded archives into the pruner in the first place.

### Pick 5 — Provider error classification  `MEDIUM value / LOW effort`
**File:** `src/engine/llm/claude_provider.py`  
The Anthropic provider retries on API errors.  Distinguish usage-limit HTTP 429 responses (body contains `"type":"usage_limit_exceeded"`) from rate-limit 429s and raise them immediately without entering the retry loop.

---

## My Picks for Next Spikes

**Spike now:** Pick 1 (tool-failure reporting in `src/engine/runner.py`).  One-file change, high correctness payoff, easy to validate with a unit test: dispatch a tool call with a missing handler, assert the run surfaces an error rather than succeeding.

**Spike next:** Pick 2 (credential redaction in `src/shared/config.py`).  Straightforward regex pass; prevents accidental key leaks in log output.  Pairs naturally with any upcoming logging-verbosity work.

**Defer:** Picks 3–5 are good hygiene but no acute pain point; pick them up in a tightening pass once Picks 1–2 are landed.

---

*Sources: [github.com/openclaw/openclaw/releases](https://github.com/openclaw/openclaw/releases), [docs.openclaw.ai](https://docs.openclaw.ai)*
