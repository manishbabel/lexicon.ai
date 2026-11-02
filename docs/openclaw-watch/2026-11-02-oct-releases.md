# OpenClaw Watch — 2026-11-02

_Covers releases since last-checked 2026-09-23. Sources: github.com/openclaw/openclaw/releases._

---

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.10.10-beta.5 | 30 Oct 2026 | Beta | Node 24/26 fixes, cron catch-up after restart, exec allowlist tightening |
| 2026.10.9 | 29 Oct 2026 | **Stable (latest)** | SQLite memory recovery, disk-full runtime resilience, credential scrubbing, skill YAML fix |
| 2026.10.10-beta.4 | 27 Oct 2026 | Beta | Scheduled follow-up authority chain, Memory Wiki note preservation, hooks.token scrubbing |
| 2026.9.36 | 29 Oct 2026 | Extended-stable (gateway only) | workspaceOnly gateway tools, Teams allowlist hardening, untrusted-input parsing bounds |
| 2026.10.1–2026.10.8 | Oct 2026 | Stable | Intermediate stable train (full notes at docs.openclaw.ai/releases) |
| 2026.9.1–2026.9.35 | Sep 2026 | Stable | September stable train |

---

## What's notable

### 1. Stale-cron slot recovery (`2026.10.10-beta.5`)
Cron dropped missed slots when the stored `next_run` timestamp was stale after a restart. The fix computes catch-up eligibility against wall-clock time and admits missed slots up to a configurable backfill window. This is a correctness bug, not a feature: any persistent scheduler that stores absolute next-run times is vulnerable.

### 2. Scheduled follow-up authority chain (`2026.10.10-beta.4`)
Explicit same-conversation scheduled follow-ups now carry the original operator's auth context — approval level, tool-policy boundaries, and cancellation — through to the fired turn. Previously, fired crons could silently escalate or drop permissions depending on session state at fire time.

### 3. workspaceOnly isolation for Gateway-built tools (`2026.10.9`, `2026.9.36`)
Tools created dynamically by the gateway at session time now receive the same `workspaceOnly` workspace-scope restriction as statically registered tools. Unresolved allowlists (Teams, etc.) stay restrictive rather than falling open. This closes a class of lateral-movement paths through runtime-registered tools.

### 4. Credential scrubbing from logs and CLI inspection (`2026.10.9`, `2026.10.10-beta.4`)
OAuth client secrets, MCP CLI inspection output, and the `hooks.token` environment variable are now masked before reaching log sinks and child-process environments. The pattern: scrub at the logger/env-builder boundary, not at each callsite.

### 5. Memory Wiki note preservation on re-import (`2026.10.10-beta.4`)
When concept pages are re-imported or removed, human-authored notes attached to those pages now survive. Previously, a re-import cycle silently discarded any edits made after the initial import.

---

## What we can use in Lexicon

Ranked by value × effort (high-value, low-effort first). Every path verified to exist in this repo.

### [P1] Stale-cron slot recovery — **High value / Low effort**
- **Pattern:** On scheduler startup, compare stored `next_run` against `now()`. If stale by more than one interval, compute catch-up slots rather than skipping them.
- **Lexicon file:** `src/cron/scheduler.py` — the `_tick()` / next-run advance logic.
- **Also touch:** `src/cron/store.py` — where `next_run` is persisted; add a `last_fired_at` column to allow drift detection.
- **Why now:** If Lexicon's cron process restarts (deploy, OOM kill), any persistent jobs will silently skip their missed window. Low risk to port.

### [P2] Credential scrubbing at logger boundary — **High value / Low effort**
- **Pattern:** Single scrub pass in the logger before any sink write; extend to env-builder for child processes.
- **Lexicon file:** `src/shared/logger.py` — add a `_scrub()` filter that redacts known secret patterns (Bearer tokens, `client_secret`, `hooks.token`, OAuth credentials).
- **Why now:** Lexicon already routes through a central logger. One addition, broad coverage.

### [P3] workspaceOnly for dynamically registered gateway tools — **Medium value / Medium effort**
- **Pattern:** When a tool is registered at session build time (as opposed to statically at startup), tag it `workspace_only=True` and reject cross-workspace calls at dispatch.
- **Lexicon file:** `src/gateway/server.py` — tool registration path.
- **Also touch:** `src/gateway/router.py` — add workspace-scope check before dispatch.
- **Why now:** Lexicon's gateway builds per-session tool sets; the isolation gap is real.

### [P4] Scheduled follow-up authority chain — **Medium value / Medium effort**
- **Pattern:** Serialize the operator's auth context (approval level + tool-policy) into the cron job record at schedule time; restore it as the firing context rather than inheriting ambient session state.
- **Lexicon file:** `src/cron/scheduler.py` — `schedule()` and `_fire()`.
- **Also touch:** `src/cron/store.py` — add `auth_context` JSON column to job records.
- **Why now:** Lexicon supports scheduled agent tasks; a deploy between schedule and fire can shift ambient permissions.

### [P5] Memory note preservation on re-import — **Low value / Low effort**
- **Pattern:** Before overwriting a memory entry during import, diff against existing human-authored fields and merge rather than replace.
- **Lexicon file:** `src/engine/memory/manager.py` — the upsert path in `store()` or equivalent.
- **Why now:** Small defensive change; prevents accidental data loss on memory refresh cycles.

---

## My picks for what to spike next

1. **P1 (stale-cron recovery in `src/cron/scheduler.py`)** — correctness bug with no design ambiguity; spike is a focused patch to `_tick()` and `store.py`.
2. **P2 (credential scrubbing in `src/shared/logger.py`)** — ten-line addition, immediate security posture improvement.
3. **P3 (gateway workspaceOnly)** — worth a design spike before coding; the scope of dynamic tool registration in Lexicon needs a quick audit first.
