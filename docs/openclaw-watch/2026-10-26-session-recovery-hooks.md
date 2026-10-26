# OpenClaw Watch — 2026-10-26

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.10.7** | Oct 24, 2026 | Stable (Latest) | Session recovery, atomic patches, bounded child-context, duplicate-wake prevention, incremental plugin loading, Gemini 4 Argon |
| **2026.9.34** | Oct 24, 2026 | Extended-stable (LTS equivalent) | `apply_patch` pre-validation, `before_tool_call` hooks, Memory Wiki note preservation, managed plugin convergence, dep patches (zod, body-parser) |
| **2026.10.10-beta.3** | Oct 21, 2026 | Beta | Windows state init fixes, Gateway startup recovery |

Previous state: stable `2026.5.27`, beta `2026.5.28-beta.2` (last checked 2026-09-23). Everything above is new.

---

## What's notable

**1. `before_tool_call` hooks (2026.9.34)**
Hooks now fire *before* each tool invocation during `openclaw agent exec`, giving operators a pre-execution interception point. Previously only post-tool hooks were reliable. This enables audit logging, rate-limit enforcement, and tool-call rewriting without patching the runtime core.

**2. Atomic multi-file patch validation (2026.10.7, 2026.9.34)**
`apply_patch` validates the full ordered diff before writing any file. A bad hunk in file N no longer leaves files 1…N-1 partially written. The pattern is: parse and validate all hunks → only then open any file for write → on first write failure roll back by leaving already-written files via backup swap.

**3. Memory re-import preserving human-authored notes (2026.10.7, 2026.9.34)**
OKF (knowledge-framework) re-imports now detect and preserve notes tagged as human-authored, skipping the overwrite that previously wiped them. The distinguishing mechanism is a provenance marker on each memory record (system-generated vs. user-written).

**4. Replay-safe session recovery (2026.10.7)**
Interrupted sessions keep a recovery-provenance record of unfinished tool outcomes. On restart the runtime checks for this record and replays only the missing steps rather than re-running from scratch or silently dropping the result. Terminal cleanup on stop clears stale recovery state before the next message is accepted.

**5. Bounded context for child-task completions (2026.10.7)**
Large batches of child-task completion events are chunked to stay within the parent agent's context limit. Previously a wide fan-out of sub-tasks could flood the orchestrator context and force a compaction that lost intermediate results.

---

## What we can use in Lexicon

Ranked by value/effort (HIGH/MED/LOW).

| # | Pattern | Value | Effort | Lexicon files |
|---|---|---|---|---|
| 1 | **`before_tool_call` hooks** — pre-execution interception point for every tool call | HIGH | MED | `src/engine/hooks/registry.py`, `src/engine/hooks/loader.py`, `src/engine/hooks/builtin.py` |
| 2 | **Atomic vault write validation** — validate full write intent before opening any file | HIGH | LOW | `src/engine/tools/vault_write.py` |
| 3 | **Human-authored memory preservation** — provenance marker on memory records to survive re-imports | MED | LOW | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py` |
| 4 | **Replay-safe runner recovery** — recovery-provenance record on runner state, check on restart | HIGH | HIGH | `src/engine/runner.py`, `src/gateway/session.py` |
| 5 | **Bounded child-task context** — chunk orchestrator completion events to respect context limit | MED | MED | `src/engine/context/pruner.py`, `src/engine/context/compactor.py` |

---

## Picks for what to spike next

**Spike 1 (low-hanging): Atomic vault write validation**
`src/engine/tools/vault_write.py` currently opens and writes files without pre-validating that all paths are writable and that no write will conflict. Port the pattern: collect all intended writes, validate each path, then execute. Cost: ~30 lines. Risk: minimal — it's a pure quality improvement with no API change.

**Spike 2 (highest leverage): `before_tool_call` hooks**
Lexicon already has `src/engine/hooks/registry.py` with a registration mechanism and `src/engine/hooks/loader.py` for hook discovery. Adding a `before_tool_call` dispatch point in `src/engine/runner.py` (where tool calls are dispatched) would let operators attach audit, rate-limit, or rewrite hooks without touching the runtime. Pairs naturally with `src/engine/tools/registry.py` which already enumerates available tools.
