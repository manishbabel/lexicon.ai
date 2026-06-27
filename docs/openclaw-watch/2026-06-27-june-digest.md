# OpenClaw Watch — June 27 2026

## What Shipped

| Release | Date | Type |
|---|---|---|
| **2026.6.10** | 2026-06-24 | Stable |
| 2026.6.11-beta.1 | 2026-06-24 | Beta |
| 2026.6.10-beta.2 | 2026-06-22 | Beta |
| 2026.6.10-beta.1 | 2026-06-21 | Beta |

Previous baseline: stable `2026.5.27` / beta `2026.5.28-beta.2`

### 2026.6.10 (stable) — headline changes
- **Automatic fast mode**: short conversational turns enter a fast path automatically; longer or fallback work returns to normal runtime without losing visible state or delivery context.
- **Cross-channel session identity**: channel switches now reset stale origin fields; cron delivery awareness stays attached to the target session across reconnects.
- **Provider routing hardening**: tighter model synthesis (Zai), GLM overload failover, and native reasoning-level selection pulled from the active runtime catalog at turn time.
- **Delivery reliability**: Telegram/WhatsApp/Slack retry surfaces now preserve fast-mode state across progress events and ACP/CLI normalization.

### 2026.6.11-beta.1 — headline changes
- **Slack relay mode + native Mattermost `/oc_queue`**: channel adapters can relay rather than originate; Mattermost gets a first-class queue command.
- **Externalized official plugins**: the plugin distribution boundary moves out of the core bundle; icon metadata ships separately to installed clients.
- **File-driven agent invocation**: `--message-file` flag on the agent CLI lets operators drive turns from files rather than inline args.
- **Prompt-cache stability for long contexts**: Codex partial deltas + cache-stable prompt construction reduce dropped progress on long-running turns.
- **Android settings panels**: configuration visibility and control improvements on mobile — not relevant for Lexicon.

---

## What's Notable

### 1. Two-tier turn routing (fast mode)
OpenClaw now classifies each incoming turn before dispatching it. Short/conversational turns skip the full agent spin-up and return on a fast path; only longer or fallback turns pay the full runtime cost. State (session, delivery context, progress events) survives the tier boundary in both directions. This is a clean runtime pattern: classify → dispatch-tier → merge-state.

### 2. Session-aware cron delivery
Cron jobs now carry a reference to the originating session/channel, so delivery context (which channel, which user) stays attached through retry and reconnect cycles. Previously, a reconnect could lose the target and deliver to the wrong destination.

### 3. Externalized plugin boundary
Official plugins move out of the core distributable. The core exposes a stable extension point; plugin icon metadata is bundled separately. This is a distribution/boundary pattern, not just packaging — it enforces that the core runtime doesn't grow with each new plugin.

### 4. Prompt-cache stability under long context
Codex partial-delta streaming is combined with a cache-stable prompt layout to prevent context loss on long turns. The pattern is: structure the prompt so the cached prefix is immutable across turns; stream deltas against that stable anchor.

### 5. Per-DM model overrides via channel config
Channel operators can now set a model override at the DM level — the model is resolved from channel config before falling through to the global runtime catalog. This is a layered routing pattern: channel-config → operator-config → runtime-default.

---

## What We Can Use in Lexicon

Ranked by value/effort. Each maps to a file that exists in `src/`.

### 1. Two-tier turn routing — `src/engine/runtime.py` + `src/engine/llm/router.py`
**Value: High / Effort: Medium**

Lexicon's `runtime.py` dispatches every turn through the same path regardless of complexity. A fast tier — classify turn length/type at entry, skip agent orchestration for short conversational replies, merge state on return — would reduce latency for the majority of meeting-copilot turns that are short clarification replies. The LLM router (`src/engine/llm/router.py`) already picks providers; adding a tier selection upstream is a natural extension.

### 2. Cache-stable prompt layout — `src/engine/context/compactor.py` + `src/engine/context/pruner.py`
**Value: High / Effort: Low–Medium**

Lexicon already has a compactor and pruner. The OpenClaw pattern adds one constraint: the cached prefix (system prompt + static context) must be immutable across turns so the provider can cache it. If `compactor.py` currently rebuilds the prefix dynamically on each turn, pinning the stable portion would reduce token spend on long meetings where the system prompt is large and repeated.

### 3. Session-scoped cron delivery — `src/cron/scheduler.py` + `src/gateway/session.py`
**Value: Medium / Effort: Low**

Lexicon's cron scheduler (`src/cron/scheduler.py`) fires jobs but the delivery target may be resolved at fire time rather than capture time. Attaching the originating session reference at schedule time (mirroring OpenClaw's fix) ensures cron-triggered notifications reach the right meeting session even after a WebSocket reconnect. The `gateway/session.py` already tracks sessions; this is a wiring change.

### 4. Externalized tool/skill boundary — `src/engine/skills.py` + `src/engine/tools/registry.py`
**Value: Medium / Effort: Medium**

Lexicon's tools and skills are registered centrally (`tools/registry.py`, `skills.py`). The OpenClaw pattern of externalizing official plugins behind a stable extension point would let Lexicon ship core separately from domain-specific tools (e.g., Obsidian, RSS, vault tools), reducing core startup cost and making tool sets swappable per deployment.

### 5. Layered model routing — `src/engine/llm/router.py`
**Value: Low–Medium / Effort: Low**

The per-DM model override pattern maps to a per-session or per-agent model override in Lexicon: resolve model from session config first, fall through to the global router default. The `llm/router.py` is the right place; it's a small addition with meaningful operational value for multi-tenant or per-user model selection.

---

## My Picks for What to Spike Next

**Spike 1 (highest ROI): Cache-stable prompt layout in `src/engine/context/compactor.py`**
Low effort, measurable impact for every meeting session. Check whether `compactor.py` rebuilds the system-prompt prefix on each turn; if so, pin it. Pair with `src/engine/context/token_counter.py` to verify cache hit rates before and after.

**Spike 2: Two-tier turn routing in `src/engine/runtime.py`**
Medium effort but the most architecturally interesting pattern from this batch. Short conversational turns (e.g., "what was that last point?") account for a large fraction of meeting-copilot traffic. A fast path that skips `orchestrator.py` and goes straight to `llm/router.py` would be measurable in p50 latency.
