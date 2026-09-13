# OpenClaw Watch — 2026-09-13: Runtime Safety & Delivery

## What shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.9.4** | 2026-09-11 | Stable | Build/packaging validation pass; 1,558 PRs merged in cycle |
| **2026.9.3** | 2026-09-08 | Stable | Isolated state rehearsal, warm cache preservation, Skill Workshop persistent collections, Team Reports plugin, public transcripts with revocable access |
| **2026.6.35** | 2026-09-10 | LTS | Final June Extended Stable: safer provider/channel boundaries, reliable cancellation handling, bundled-plugin resilience, malformed-input rejection |

Previous stable baseline: **2026.5.27** (2026-05-27). Three report-worthy releases since.

No new beta beyond **2026.5.28-beta.2** (releasebot.io and docs.openclaw.ai unreachable from this env; using github.com/openclaw/openclaw/releases as sole source).

---

## What's notable

### 1. Isolated candidate state rehearsal (2026.9.3)
Before activating a core state change (scheduler reconfiguration, runtime context swap), OpenClaw now clones current live state into a "candidate," applies the change to the clone, runs a lightweight rehearsal tick, and only promotes the candidate to live if rehearsal passes. Failures discard the candidate without touching the live state. This eliminates half-applied state from interleaved updates or partial failures.

### 2. Warm prompt-cache preservation across cold updates (2026.9.3)
Session updates that would previously bust all cached prompt prefixes now track which cache entries remain valid (same model, same prefix hash) and carry them forward. Avoids redundant LLM round-trips when a session is interrupted and resumed. Paired with reduced unnecessary context re-serialisation during cold starts.

### 3. Safer provider and channel boundaries — bounded untrusted response bodies (2026.6.35 LTS)
Bundled providers now apply a size cap and lightweight sanitisation to untrusted response bodies *before* handing them to the engine. Previously an oversized or malformed provider response could propagate through the runtime and crash an otherwise healthy agent run. The fix is at the provider abstraction layer, not in each integration.

### 4. Reliable long-running delivery under cancellation (2026.6.35 LTS)
Agent, gateway, and retry paths now handle cancellation signals without discarding in-flight work. Queued items are checkpointed or re-enqueued rather than silently dropped when a run is cancelled or a worker exits mid-delivery.

### 5. Malformed/oversized input rejection at the tools boundary (2026.6.35 LTS)
Tool and workspace entry points now validate and reject malformed or oversized inputs *before* they reach the running agent, preventing a bad tool call from interrupting an otherwise healthy session. The check runs at the tool-registry dispatch layer.

---

## What we can use in Lexicon

Ranked by value / effort (V = value 1–5, E = effort 1–5 where 1 is lowest):

| # | Pattern | V | E | Lexicon target |
|---|---|---|---|---|
| 1 | **Bounded provider response bodies** | 5 | 1 | `src/engine/llm/provider.py` — add size cap + sanitisation before returning to router |
| 2 | **Malformed input rejection at tools boundary** | 4 | 1 | `src/engine/tools/registry.py` — validate/reject before dispatch; also `src/gateway/protocol.py` at inbound decode |
| 3 | **Isolated candidate state rehearsal** | 5 | 3 | `src/engine/runtime.py` — stage session-state mutations on a clone; `src/cron/scheduler.py` — rehearse new job configs before activating |
| 4 | **Warm prompt-cache preservation** | 4 | 3 | `src/engine/context/pruner.py` + `src/engine/context/compactor.py` — track prefix-hash validity before pruning so warm entries survive context compaction |
| 5 | **Cancellation-safe delivery** | 3 | 3 | `src/engine/queue.py` + `src/engine/runner.py` — checkpoint or re-enqueue in-flight items on cancellation rather than dropping |

All target files verified to exist under `src/`.

---

## Picks to spike next

**Spike 1 — Bounded provider response bodies** (`src/engine/llm/provider.py`):
Highest value-to-effort ratio. A single guard at the abstract provider base prevents every concrete provider (OpenAI, Claude, LiteLLM) from propagating oversized responses into the runtime. Easy to add, hard to forget once in.

**Spike 2 — Malformed input rejection at tools boundary** (`src/engine/tools/registry.py`):
Complements Spike 1 on the inbound side. Both can land in the same PR with near-zero risk.

**Spike 3 — Isolated candidate state rehearsal** (`src/engine/runtime.py`):
Bigger lift but addresses a real class of intermittent bugs where partial state updates leave the runtime in an inconsistent state during hot reloads or scheduler reconfiguration.
