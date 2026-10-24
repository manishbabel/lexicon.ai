# OpenClaw Watch: 2026-10-24 Digest

**Versions covered:** 2026.6.1 → 2026.10.7 (stable), 2026.10.10-beta.3 (beta)
**Previous baseline:** 2026.5.27 (stable), 2026.5.28-beta.2 (beta)
**Sources:** github.com/openclaw/openclaw/releases

---

## What Shipped

| Version | Date | Type | Headline |
|---------|------|------|----------|
| 2026.6.1 | June 2026 | Stable | Skills workshop review pipeline; SQLite state migration; resilient agent runs; per-plugin isolation |
| 2026.8.2 | August 2026 | Stable | Cross-session visibility; plugin SDK deprecations; secret redaction in logs; MCP response limits; long-history perf |
| 2026.9.34 | Sep–Oct 2026 | Extended-stable (LTS) | `apply_patch` atomic validation; Node runtime floors; Memory Wiki note preservation; hook lifecycle fixes |
| 2026.10.6 | 22 Oct 2026 | Stable | Node security floor enforcement; reliability-only patch, no new features |
| 2026.10.7 | 24 Oct 2026 | Stable (latest) | Session recovery after interruptions; DB/worker stability; Gemini 4 Argon support; macOS onboarding fix |
| 2026.10.10-beta.3 | 21 Oct 2026 | Pre-release | Windows state init; upgrade recovery for plugins; concurrent agent-DB ownership bug; Discord slash commands |

---

## What's Notable

### 1. Atomic ordered-edit validation before any mutation (2026.9.34)
`apply_patch` now validates the entire ordered envelope—all hunks in sequence—before touching the workspace. A later invalid hunk can no longer delete files that an earlier hunk already wrote. This is a preflight-or-abort pattern for multi-step file mutations.

### 2. Guarded skill proposals with review pipeline (2026.6.1)
Skills authored by agents enter a pending state and require explicit operator review (apply / reject / quarantine) before activation. Proposals carry versioned metadata and rollback info. Disabled skills can no longer inject stale environment overrides that abort unrelated turns.

### 3. Per-plugin failure isolation (2026.6.1 / 2026.8.2)
Plugin catalog projection and provider factory errors are contained at the plugin boundary: one failing plugin cannot poison sibling plugins or the shared runtime. Combined with 2026.8.2's capability-review gate (new capabilities block until reviewed, old plugin retained), this makes the plugin lifecycle substantially more robust.

### 4. Hook lifecycle parity across all execution paths (2026.9.34)
`before_tool_call` hooks regressed silently when running under `openclaw agent exec` (a secondary entry point). The fix required explicitly wiring hooks into every execution path—the lesson being that lifecycle hooks need explicit tests on non-primary paths.

### 5. Redaction and bounds as first-class primitives (2026.8.2)
Secret values are marked at creation and redacted at every sink (macOS logs, trajectory exports, diagnostics). MCP/HTTP response and SSE event sizes are rejected before parsing. Per-client admission caps on relay authentication prevent capacity exhaustion by a single noisy source.

---

## What We Can Use in Lexicon

Ordered by value-to-effort ratio. All file paths verified against the repo.

### 1. Preflight multi-step vault writes (HIGH value / LOW effort)
**OpenClaw pattern:** Validate the full ordered edit set before applying any hunk.
**Lexicon file:** `src/vault/writer.py`
Before committing a list of vault edits (append, overwrite, search-replace), validate all of them in a dry-run pass and abort the whole batch on the first failure. Prevents partial corruption where early writes succeed and a later bad write leaves the vault in an inconsistent state.

### 2. Hook wiring audit across all runner entry points (HIGH / MEDIUM)
**OpenClaw pattern:** `before_tool_call` silently dropped from secondary entry point.
**Lexicon files:** `src/engine/runner.py`, `src/engine/hooks/registry.py`
The runner has at least two call paths (direct invocation and orchestrator-dispatched). Audit that `src/engine/hooks/loader.py` and `src/engine/hooks/registry.py` are invoked on all of them, not just the primary path. Add a test that fires a no-op hook via the orchestrator path to catch future regressions.

### 3. Per-store write serialization in cron store (MEDIUM / LOW)
**OpenClaw pattern:** QMD index writes serialized per store to avoid SQLite lock contention.
**Lexicon file:** `src/cron/store.py`
If `src/cron/store.py` uses SQLite and accepts concurrent writes (from scheduler + cron defaults loading), add a per-store asyncio lock or `check_same_thread=False` + connection-level mutex to serialize writes. Prevents `database is locked` errors under concurrent cron tick + config reload.

### 4. Redact secrets at the logger, not at the call site (MEDIUM / LOW)
**OpenClaw pattern:** Mark sensitive values at creation; every log sink respects the mark.
**Lexicon file:** `src/shared/logger.py`
Add a `redact=` kwarg (or a `SecretStr` wrapper type in `src/shared/types.py`) so that any value flagged as sensitive is masked before it reaches any log handler. Prevents provider API keys and tokens that flow through `src/engine/llm/` from appearing in log files.

### 5. Guarded skill proposal state in skills loader (MEDIUM / MEDIUM)
**OpenClaw pattern:** Agent-authored skill proposals require explicit review before activation.
**Lexicon file:** `src/engine/skills.py`
Add a `status` field (active / pending / disabled) to skill frontmatter (parsed in `src/shared/frontmatter.py`) and gate skill loading on `status == active`. Skills created at runtime by agents land in `pending` and require a human `approve` action. Low-cost safety fence against runaway self-modification.

---

## My Picks for Next Spike

1. **`src/vault/writer.py` — atomic preflight** (1–2 hours, high safety value, no new dependencies)
2. **`src/engine/runner.py` — hook wiring audit** (2–3 hours including test; closes a silent correctness hole that's bit OpenClaw in production)
3. **`src/shared/logger.py` — secret redaction** (2–4 hours; straightforward but easy to get wrong — worth doing deliberately)
