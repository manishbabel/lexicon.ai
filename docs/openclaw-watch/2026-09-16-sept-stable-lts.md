# OpenClaw Watch — 2026-09-16: September Stable + June LTS Final

**Digest date:** 2026-09-16
**Versions covered:** 2026.6.35 (LTS final), 2026.9.3, 2026.9.4 (stable)
**Previous baseline:** stable 2026.5.27 / beta 2026.5.28-beta.2

---

## What Shipped

| Version | Released | Type | Headline |
|---|---|---|---|
| **2026.9.4** | 2026-09-11 | Stable | Distribution + verification release; 20 direct commits, 1,558 PRs from 294 contributors |
| **2026.6.35** | 2026-09-10 | LTS Final | Last June 2026 Extended Stable; safety and reliability hardening |
| **2026.9.3** | 2026-09-08 | Stable | Isolated update staging, warm cache preservation, agent-owned skill collections, session transcripts |
| **2026.8.1-beta.{2,3,4}** | Aug–Sep | Beta | Pre-release ramp to 2026.9.x; mistakenly versioned, now superseded |

### 2026.6.35 LTS — Key Changes
- **Provider and channel input bounding** (#119942): bundled providers and channel adapters now reject oversized inputs before expensive work begins; untrusted response bodies are size-capped.
- **Memory/response read caps**: successful and error response reads bounded to prevent hostile payload exhaustion.
- **Delivery recovery hardening**: retry timing, channel lifecycle, and process I/O all more resilient across agent, gateway, and channel paths.
- **Tool/workspace input validation**: inputs validated before agent execution begins.

### 2026.9.3 — Key Changes
- **Isolated candidate state for updates** (#138839): core and plugin changes rehearsed in isolated state before activation; supports eligible 2026.9.2 migrations.
- **Warm prompt cache preservation**: prompt caches kept warm during cold session updates; unnecessary work reduced.
- **Agent-owned Workshop skills**: skill collections now owned per-agent with persistence across workspaces (replaces workspace ownership).
- **Public session transcripts**: revocable read-only sharing of session transcripts; searchable meeting library with downloads.
- **Breaking**: Node 24.16.0+ / 26.1.0+ required; `execution-policy` and approval SDK restructured; search result callbacks now read from `details.content`.

---

## What's Notable

### 1. Provider/Channel Input Bounding (2026.6.35 #119942)
Before any expensive LLM call or channel operation, OpenClaw now checks the request size and caps response reads. This is a systematic defense: reject at ingress rather than OOM at execution. Both the provider layer and the channel/gateway layer get the same treatment.

### 2. Memory Safety via Bounded Reads (2026.6.35)
Response bodies — both success and error paths — are capped before they reach memory. The pattern prevents a hostile or runaway upstream from exhausting context budget or blowing stack. Complements compaction but is orthogonal: compaction manages budget after the fact; bounded reads prevent budget violations at source.

### 3. Isolated Candidate State for Runtime Updates (2026.9.3 #138839)
When OpenClaw updates itself or a plugin, the new code is staged in an isolated candidate environment and exercised (including migrations) before it replaces the live runtime. The live runtime stays up until candidate validation passes. This is a blue/green-style hot-update pattern applied to an agent runtime.

### 4. Warm Prompt Cache Preservation During Cold Updates (2026.9.3)
Cache warmth is treated as a first-class resource: session updates avoid invalidating prompt caches unless forced. The scheduling layer coordinates update timing to minimize cold restarts.

### 5. Agent-Owned Skill Collections with Cross-Workspace Persistence (2026.9.3)
Skills are no longer scoped to a workspace folder hierarchy — they follow the agent identity, persisting across workspace changes. The ownership model decouples skill state from filesystem layout.

---

## What We Can Use in Lexicon

Ranked by value/effort. Each entry maps to a real file under `src/`.

### 1. Provider input-size guard — HIGH value / LOW effort
**Pattern:** cap `max_tokens`, `messages` byte size, and `tools` payload before calling `.stream()`.
**File:** `src/engine/llm/provider.py:11` (`LLMProvider.stream` signature)
**Also touches:** `src/engine/llm/claude_provider.py`, `src/engine/llm/openai_provider.py`, `src/engine/llm/litellm_provider.py`
**What to add:** validate `len(json.dumps(messages))` and `max_tokens` against configurable limits in the base `stream()` before dispatching to each concrete provider. One guard in the abstract base protects all providers.

### 2. Channel/gateway response body cap — HIGH value / LOW effort
**Pattern:** wrap response reads in a `BytesLimitedReader` (or equivalent async generator wrapper) before the payload reaches session or memory.
**File:** `src/gateway/session.py`
**Also touches:** `src/gateway/server.py`, `src/gateway/router.py`
**What to add:** a size cap on raw inbound messages (e.g. 512 KB) in the session receive loop, rejected before parse.

### 3. Bounded error-response reads in memory — HIGH value / LOW effort
**Pattern:** cap LLM error payloads before they're written into episodic or short-term memory.
**Files:** `src/engine/memory/manager.py`, `src/engine/memory/episodic.py`, `src/engine/memory/short_term.py`
**What to add:** truncate or drop oversized error responses at the memory write boundary. The compactor (`src/engine/context/compactor.py:7`) already strips tool result details before LLM summarisation — extend the same discipline to the write path.

### 4. Warm cache preservation during context compaction — MEDIUM value / MEDIUM effort
**Pattern:** before compacting, check whether the current token budget allows the existing cache prefix to survive; defer compaction if evicting it would cost more than keeping old messages.
**Files:** `src/engine/context/compactor.py`, `src/engine/context/pruner.py`
**What to add:** a `cache_prefix_tokens` field on the compaction decision; skip compaction if it would evict a warm prefix unless budget is critical.

### 5. Agent-owned skill persistence across workspace switches — MEDIUM value / MEDIUM effort
**Pattern:** decouple skill ownership from `~/.lexicon/workspaces/<persona>/skills/` path and bind it to the agent identity (persona name) in a flat agent-skills store.
**File:** `src/engine/skills.py:1` (three-tier precedence is currently path-based)
**What to add:** a Tier 0 above the current Tier 3 — an agent-identity-keyed store in `~/.lexicon/agents/<persona>/skills/` that survives workspace renames and moves. The hot-reload watchfiles already present makes adding a fourth watched directory straightforward.

---

## My Picks for Next Spike

**Spike 1 (this week): Provider input-size guard** (`src/engine/llm/provider.py`)
Highest signal/noise ratio — one `if len(...) > MAX_BYTES: raise` in `LLMProvider.stream()` protects every concrete provider. Zero new abstractions needed. Can ship in a single small PR.

**Spike 2 (this sprint): Gateway message size cap** (`src/gateway/session.py`)
Second-cheapest, highest blast-radius fix. An unbounded inbound message can crash the runtime before any business logic runs. Pair with the provider guard for end-to-end coverage.

**Spike 3 (next sprint): Bounded memory writes** (`src/engine/memory/manager.py`)
The compactor already has the right instinct (`src/engine/context/compactor.py:7`). Extend it to the write path. Medium effort but closes the loop on the memory safety story.
