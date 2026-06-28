# OpenClaw Watch — 2026-06-28: June Runtime Hardening

**Baseline:** stable `2026.5.27` / beta `2026.5.28-beta.2`
**Checked:** 2026-06-28

---

## What Shipped

### Stable

| Version | Date | Headline |
|---------|------|---------|
| 2026.6.1 | Jun 3 | Resilient agent recovery, SQLite cron persistence, skill governance workshop, plugin fault isolation |
| 2026.6.6 | Jun 12 | Fail-closed security across exec/MCP/sandbox paths, Claude Fable 5 + adaptive thinking, cron cancellation/stagger |
| 2026.6.9 | Jun 21 | Channel plugins as first-class external packages, OpenTelemetry log export, session workspace rails, skill install provenance |

### Beta

| Version | Date | Headline |
|---------|------|---------|
| 2026.6.11-beta.1 | Jun 24 | Session-accessor memory pattern, memory artifact sanitization before persistence, provider response body bounding, Slack relay mode, per-DM model overrides |

---

## What's Notable

**1. Cron retry on model rate limits (2026.6.1)**
Recurring jobs now retry after transient LLM rate-limit errors before surrendering the scheduled slot. Previously, a rate limit on slot N would silently drop the run until slot N+1. The fix: a short back-off loop inside the job executor, transparent to the schedule definition. Directly applicable to any heartbeat or cron-driven agent loop.

**2. Plugin fault isolation for LLM providers (2026.6.1)**
Private LLM-core declarations are now bundled separately from provider plugins. A broken or misbehaving provider can no longer poison the import path of sibling providers. The pattern: each provider is loaded in an isolated scope; the router catches import-time exceptions per-provider, marks that provider degraded, and routes around it rather than crashing the whole runtime.

**3. Fail-closed security across exec/tool/MCP paths (2026.6.6)**
Transcript, sandbox, MCP, browser, channel, and exec-approval paths all now fail closed (deny by default) when they encounter unsafe access or malformed inputs—rather than logging and proceeding. Env variable denylist expanded; non-owner loopback tool restrictions added; sandbox bind-mount validation enforced. This is a posture shift, not a one-off patch.

**4. Memory artifact sanitization before persistence (2026.6.11-beta.1)**
Memory artifacts (episodic entries, transcript fragments, dreaming narratives) are now sanitized before write to prevent prompt-injection via stored memory. Companion change: a session-accessor interface centralizes all memory read/write operations through a single boundary, making it easier to add validation or audit hooks without touching every callsite.

**5. Claude Fable 5 adaptive thinking support (2026.6.6)**
The Claude Fable 5 model is now registered as a first-class provider with adaptive thinking (extended reasoning) surfaced as an opt-in parameter. Provider normalization also landed for ACP model references and local execution without guardian review.

---

## What We Can Use in Lexicon

Ranked by value / effort. All file paths verified against `src/` tree.

| # | Pattern | Source release | Value | Effort | Lexicon file(s) |
|---|---------|---------------|-------|--------|----------------|
| 1 | **Cron retry on rate limits** — back-off loop before surrendering the slot | 2026.6.1 | High | Low | `src/cron/scheduler.py` |
| 2 | **Claude Fable 5 + adaptive thinking** — register model, forward `thinking` param | 2026.6.6 | High | Low | `src/engine/llm/claude_provider.py`, `src/engine/llm/router.py` |
| 3 | **Fail-closed tool/exec security** — deny-by-default on unsafe inputs, env denylist expansion | 2026.6.6 | High | Medium | `src/engine/tools/registry.py`, `src/gateway/server.py` |
| 4 | **Memory artifact sanitization** — sanitize before write, session-accessor boundary | 2026.6.11-beta.1 | High | Medium | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py` |
| 5 | **Provider fault isolation** — per-provider import scope, degrade-and-route-around | 2026.6.1 | High | Medium | `src/engine/llm/router.py` |
| 6 | **Provider response body bounding** — cap streamed response bytes to prevent memory exhaustion | 2026.6.11-beta.1 | Medium | Low | `src/engine/llm/claude_provider.py`, `src/engine/llm/litellm_provider.py` |
| 7 | **OpenTelemetry log export** — structured OTLP traces from the gateway and engine | 2026.6.9 | Medium | Medium | `src/shared/logger.py` |
| 8 | **Skill install provenance** — retain verified source hash on install, block tampered updates | 2026.6.9 | Medium | High | `src/engine/skills.py`, `src/engine/tools/registry.py` |
| 9 | **Skill governance: versioned frontmatter + rollback** — apply/reject/quarantine with rollback safeguards | 2026.6.1 | Medium | High | `src/engine/skills.py` |
| 10 | **Per-DM model overrides** — session-level model selection overriding global default | 2026.6.11-beta.1 (beta) | Medium | Medium | `src/engine/llm/router.py`, `src/gateway/session.py` |

---

## My Picks to Spike Next

**1. Cron rate-limit retry → `src/cron/scheduler.py`**
Quick win with immediate resilience payoff. Lexicon's cron scheduler currently drops a run on any LLM error. Add a retry loop (e.g. 3 attempts, exponential back-off capped at half the slot interval) before marking the run failed. Contained change, no interface changes needed.

**2. Claude Fable 5 adaptive thinking → `src/engine/llm/claude_provider.py`**
Fable 5 is the current flagship model. Registering it with thinking-budget forwarding unblocks any agent that benefits from extended reasoning (summarizer, planner, memory compactor). Low effort since the provider interface is already in place.

**3. Fail-closed tool security → `src/engine/tools/registry.py`**
The env variable denylist and non-owner loopback restriction are directly portable and address a real attack surface. Worth doing before any external deployment.
