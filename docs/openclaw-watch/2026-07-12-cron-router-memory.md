# OpenClaw Watch — 2026-07-12

## What Shipped

| Version | Date | Type |
|---------|------|------|
| 2026.6.11 | ~2026-06-11 | Stable |
| 2026.7.1-beta.1 | 2026-07-02 | Beta |
| 2026.7.1-beta.2 | 2026-07-05 | Beta |
| 2026.7.1-beta.5 | 2026-07-11 | Beta |

Baseline was 2026.5.27 (stable) / 2026.5.28-beta.2 (beta).

### 2026.6.11 (stable) — reliability and diagnostics pass

Framed as "fixing rough edges." The architecture-relevant items:

- **Memory Wiki preservation**: user-written notes survive re-ingestion/sync; only generated content is refreshed. The distinction between user-authored and system-generated memory content is now explicit in the data model.
- **Cache-boundary marker sanitization**: internal cache markers no longer leak into the `system` prompt sent to LLM providers (Google, Mistral, OpenAI Responses, Azure, ChatGPT/Codex Responses). Suggests OpenClaw does a scrub pass on the assembled system string immediately before the provider call.
- **Gateway diagnostic enrichment**: provider name, model ID, request status, and per-request timing now surface in normal-level logs, not just debug. Makes model-routing problems diagnosable in production without log-level changes.
- **CLI help latency**: help for `doctor`, `gateway`, `models`, `plugins`, `sessions`, `tasks` dropped from ~1.7s to tens of milliseconds — achieved by lazy-loading provider clients only when needed.
- **OpenTelemetry trace fix**: slash-qualified model IDs (e.g. `anthropic/claude-sonnet-5`) now emit the actual provider+model name to Langfuse/OTEL backends instead of `"unknown"`.

### 2026.7.1-beta.5 — event-driven scheduling, external harness, ClawRouter

Three large additions landed across the beta.1 → beta.5 arc:

- **Event-driven cron (`on-exit` schedules)**: a new schedule kind that fires an agent run when a watched command process exits, rather than on a time expression. Session-targeted runs can now detach cleanly from the triggering process.
- **External harness attach (`openclaw attach`)**: launches an external harness process against an already-running Gateway session. Enables Codex-style interactive workflows to be resumed and inspected without creating a new session.
- **ClawRouter plugin** (bundled provider plugin): credential-scoped dynamic model discovery; supports OpenAI-compatible, native Anthropic, and native Gemini transports in a single plugin; exposes managed budget reporting across all OpenClaw usage surfaces (CLI, mobile, web).

---

## What's Notable

**1. Event-driven scheduling is a first-class primitive.**
OpenClaw's `on-exit` trigger treats process termination as a scheduling signal, turning the cron system from a wall-clock loop into a reactive dependency graph. A job can wait for another job to finish rather than polling on an interval.

**2. Memory authorship is now a data-model property, not a convention.**
The 2026.6.11 change that preserves user notes during re-ingestion implies a `source` or `authored_by` field gates whether content is overwritten. This is a clean pattern: distinguish generated/managed content from user-written content at the storage layer.

**3. System-prompt scrubbing before provider dispatch.**
Internal markers (cache boundaries, routing hints) are stripped at the boundary between the orchestration layer and the LLM provider call. This keeps the provider interface clean and avoids prompt-injection risks from internal control tokens.

**4. ClawRouter's credential-scoped model discovery.**
Rather than a static provider→model map in config, ClawRouter asks the provider "what models do you have?" at startup (scoped to the configured credentials), then uses that live list for routing. Budget is tracked per-credential, not just per-provider.

**5. External harness as a session attachment primitive.**
`openclaw attach` decouples the interactive harness lifecycle from the session lifecycle. A session can outlive its creating harness and be reattached later — which is the same model Claude Code uses for remote execution sessions.

---

## What We Can Use in Lexicon

Ranked by value/effort ratio (value H/M/L, effort H/M/L):

### 1. Event-driven cron triggers — `src/cron/scheduler.py:138`
**Value: HIGH | Effort: LOW**

`_build_trigger()` currently handles `cron`, `every`, and `at`. Adding an `on_exit` (or `on_done`) schedule type would let jobs fire when another job finishes (use `cron:done` hook already fired at line 249) rather than on a fixed interval. The hook infrastructure is already in place — `trigger_hook("cron:done", ...)` is called for every job. A new schedule type `{"type": "on_done", "after_job": "<job_id>"}` could subscribe to that hook and enqueue a follow-up run.

**Spike**: add `on_done` to `CronJob.schedule.type` in `src/cron/store.py`, handle it in `_build_trigger()` by registering a hook listener instead of an APScheduler trigger.

### 2. Memory authorship preservation — `src/engine/memory/manager.py:214` + `src/engine/memory/short_term.py`
**Value: HIGH | Effort: LOW**

`store_note()` at line 214 writes entries with `source="note"`, but `prune()` (line 247) and any future re-indexing don't distinguish user-authored notes from auto-generated summaries. Adding a `preserve: bool = False` field to `ShortTermEntry` and checking it in `ShortTermMemory.prune()` would protect hand-written notes from eviction. Matches OpenClaw 2026.6.11's pattern exactly.

**Spike**: add `preserve` to `ShortTermEntry` in `src/engine/memory/short_term.py`; set it in `store_note()`; gate eviction on `not entry.preserve`.

### 3. System-prompt sanitization before provider call — `src/engine/llm/provider.py:19`
**Value: MEDIUM | Effort: LOW**

The `stream()` and `complete()` abstract methods receive a raw `system: str`. If Lexicon ever adds cache-boundary markers or routing annotations to the system prompt (e.g. for prompt caching), those markers should be stripped before the string reaches provider implementations. A `_sanitize_system()` helper in `LLMProvider` base class, called in concrete providers before the API call, is a one-liner guard.

**Spike**: add a `_sanitize_system(s: str) -> str` protected method to `LLMProvider` in `src/engine/llm/provider.py`; call it at the top of each provider's `stream()` and `complete()`.

### 4. Gateway routing diagnostics at INFO level — `src/gateway/server.py` + `src/engine/llm/router.py:57`
**Value: MEDIUM | Effort: LOW**

`PersonaLLMRouter.resolve()` at line 57 already logs at INFO with provider+model. But there's no timing or per-request status. A `start_time`/`elapsed_ms` field on the log entry (after streaming completes) would match OpenClaw 2026.6.11's production-diagnosable routing logs and is a 3-line change in `src/engine/llm/router.py` or wherever the runner calls the provider.

**Spike**: wrap the `stream()` call in `src/engine/runner.py` with a `time.perf_counter()` start/end and log `elapsed_ms` at INFO.

### 5. Dynamic model availability check in router — `src/engine/llm/router.py:75`
**Value: MEDIUM | Effort: HIGH**

ClawRouter discovers available models per credential at startup. `PersonaLLMRouter._get_provider()` currently only instantiates a provider; it never validates that the configured `model_name` is actually available. Adding a `provider.list_models()` abstract method and a validation pass on first use would catch misconfigured personas earlier (at startup, not mid-run).

**Spike**: add `list_models() -> list[str] | None` to `LLMProvider` in `src/engine/llm/provider.py`; call it in `resolve()` with a warning log if the model isn't in the list. Budget tracking can follow as a separate spike.

---

## My Picks for What to Spike Next

**Spike 1 (this week): Memory authorship preservation**
One field + one guard in `src/engine/memory/short_term.py`. Zero risk of regression, directly protects user data. Do it before we add more note-writing surfaces.

**Spike 2 (this week): Event-driven `on_done` cron trigger**
The hook infrastructure is already there (`cron:done` at `src/cron/scheduler.py:249`). Wiring a new schedule type to it would unlock chained agent workflows — e.g., "after the morning brief runs, start the digest job" — without polling on an interval. This is the architectural pattern most worth porting from 2026.7.1-beta series.
