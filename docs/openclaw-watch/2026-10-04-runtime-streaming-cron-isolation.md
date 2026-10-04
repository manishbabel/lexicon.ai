# OpenClaw Watch — 2026-10-04

Covering releases **2026.8.2 → 2026.9.8** (stable track) and **2026.8.33 → 2026.8.35** (extended-stable track).
Previous baseline: 2026.5.27 stable / 2026.5.28-beta.2 beta.

---

## What shipped

| Version | Date | Track | Headline |
|---|---|---|---|
| 2026.8.2 | Aug 2026 | stable | Session isolation controls, cron outcome reporting, cross-session attribution |
| 2026.8.33 | 2026-09-29 | ext-stable | New models (Fable 5.1, GPT-6 Astra, Meta Muse Spark 1.3), security hardening |
| 2026.8.35 | 2026-10-02 | ext-stable | GPT-6.1 Sol routing, cron tool allowlist isolation, skill sandbox repair |
| 2026.9.6 | 2026-09-23 | stable | 178 commits / 2 614 PRs; macOS launch-crash rebuild |
| 2026.9.7 | 2026-09-30 | stable | **518 commits / 2 818 PRs**: incremental streaming, worker thread offloading, staggered reconnect, session-write scoping |
| 2026.9.8 | 2026-10-03 | stable | 58 commits / 43 PRs; gateway patch on top of 2026.9.7 |

---

## What's notable

### 1. Incremental streaming (2026.9.7)
Replaced full-reply retransmission with incremental live-text events; raw clients now reconstruct replies from deltas. Reduces per-turn network overhead and peak memory on long conversations. This is a protocol contract change, not just an optimisation.

### 2. Worker thread I/O offloading (2026.9.7)
Cold file reads, artifact preparation, and large-upload processing were moved to background workers, keeping the Gateway thread responsive during I/O-intensive operations. The pattern is explicit separation of the event-loop hot path from blocking I/O.

### 3. Cron tool allowlist isolation (2026.8.35)
Explicit per-job tool allowlists are now preserved across stale-snapshot repair cycles without widening to the auto-generated set. Prevents a repair that silently widens cron execution surface.

### 4. Staggered reconnection (2026.9.7)
Gateway reconnection attempts are staggered with jitter after outages, preventing thundering-herd bursts when multiple sessions reconnect simultaneously.

### 5. New model routing surface (2026.8.33 / 2026.8.35)
Fable 5.1, GPT-6 Astra, Meta Muse Spark 1.3, and GPT-6.1 Sol were added across OpenAI-compatible routing, discovery, and guard-model boundaries. The pattern is uniform model-capability registration rather than provider-specific branches.

---

## What we can use in Lexicon

Ranked by value/effort (high value first).

### ★★★ Incremental streaming
**Value: High / Effort: Medium**
Lexicon's runtime currently yields full reply chunks through `src/engine/runtime.py` and passes them to `src/gateway/session.py` for dispatch. Adopting an incremental-delta protocol means the gateway emits smaller frames and clients reconstruct — lower peak memory and earlier first-byte. Also decouples the LLM stream from gateway serialisation.
- **`src/engine/runtime.py`** — change yield contract from full chunks to incremental deltas
- **`src/gateway/session.py`** — emit delta frames; accumulate only for clients that opt into full-message delivery
- **`src/gateway/server.py`** — update frame format in the WebSocket/HTTP protocol layer

### ★★★ Worker thread I/O offloading
**Value: High / Effort: Medium**
`src/gateway/server.py` currently handles inbound requests on the main event loop alongside file reads (vault, memory). Moving cold reads to async workers (or a thread pool) keeps the gateway responsive under load spikes and during memory hydration on new sessions.
- **`src/gateway/server.py`** — offload vault/memory reads to worker tasks
- **`src/engine/runner.py`** — wrap blocking I/O with `asyncio.to_thread` or a dedicated executor
- **`src/engine/memory/manager.py`** — tag hydration calls that are safe to defer

### ★★ Cron tool allowlist isolation
**Value: Medium / Effort: Low**
`src/cron/scheduler.py` builds per-job tool contexts but `src/cron/store.py` does not currently distinguish between an explicit operator-set allowlist and an auto-generated snapshot. If we ever repair a stale snapshot we may silently widen what a cron job can call.
- **`src/cron/store.py`** — add an `explicit` flag on stored allowlists; repair only auto-generated entries
- **`src/cron/scheduler.py`** — read the flag and skip widening during snapshot repair

### ★★ Staggered reconnection
**Value: Medium / Effort: Low**
`src/gateway/server.py` and `src/gateway/router.py` handle client reconnection. Without jitter, a flap that drops many sessions produces a reconnect burst. Add a small random back-off (100–500 ms) before re-subscribing session state.
- **`src/gateway/server.py`** — add jittered reconnect delay

### ★ Fable 5.1 model registration
**Value: Low–Medium / Effort: Low**
`src/engine/llm/claude_provider.py` and `src/engine/llm/router.py` carry the model catalogue. Fable 5.1 (`claude-fable-5-1`) is already released; ensure it is present in the capability/context-window registry so routing decisions can use it correctly.
- **`src/engine/llm/claude_provider.py`** — add Fable 5.1 to model registry with correct context-window and capability flags
- **`src/engine/llm/router.py`** — include in model-selection heuristics

---

## My picks for what to spike next

1. **Incremental streaming** — biggest user-visible win; also forces a clean protocol boundary between runtime and gateway that we've been wanting.
2. **Worker thread offloading** — low risk, immediate gateway stability benefit under concurrent sessions; can be done incrementally method-by-method.
3. **Cron tool allowlist isolation** — one afternoon of work, material security improvement for scheduled agents.
