# OpenClaw Watch — 2026-09-22

**Stable:** 2026.9.5 (Sep 19, 2026)  
**Beta:** 2026.9.1-beta.1 (last confirmed pre-release tag; 2026.9.5 shipped no tagged beta)  
**Previous baseline:** 2026.5.27 stable / 2026.5.28-beta.2 beta  
**Releases covered:** 2026.6.x → 2026.9.5 (roughly 4 months of output)

---

## What Shipped

| Version | Date | Headline |
|---------|------|---------|
| **2026.7.1** | ~Jul 2026 | Gateway repair paths, cron cancellation fixes, security hardening for tokens/secrets/untrusted provider responses, multi-channel delivery (Telegram live progress, Slack threads/cards, Discord voice sessions) |
| **2026.7.35** | Sep 21, 2026 | Gateway-only LTS patch: preserve bundled plugin inventory when Doctor repairs registry state |
| **2026.8.1** (OpenClaw 2.0) | Aug 2026 | Rebuilt control UI, simpler onboarding, stronger memory + session continuity, large reliability pass |
| **2026.9.1** | ~Sep 1, 2026 | Personal skill libraries (`openclaw skills library`, ZIP import, per-identity publishing); cron quarantine for malformed jobs; memory spike reduction in catalogs/resets/chat; streaming overhead down; one-shot cron retries survive startup recovery |
| **2026.9.4** | Sep 11, 2026 | Plugin and skill discovery UI; visible skill learning; cloud-worker controls |
| **2026.9.5** | Sep 19, 2026 | Plugin hot-reload without Gateway restart; guided multi-agent team setup (chief-of-staff, researcher, writer, reviewer); atomic updater validates next version before cutover; approval cards routed to originating channel |

---

## What's Notable (patterns)

### 1. Plugin hot-reload without process restart (v2026.9.5)
Plugins install and reload at runtime by reusing the published inbound registry and bundled setup code. A bug report (`#153290`) reveals the exact mechanism: on reload, the old build generation is swapped only after all live channel adapter references have drained. The key insight is that the inbound registry is stable across reloads — only the execution path swaps.

### 2. Cron job quarantine on malformed entries (v2026.9.1)
Malformed or legacy cron entries are quarantined rather than blocking Gateway boot. Separately, cancelled runs now settle gracefully without truncating retry chains, and one-shot retries survive startup recovery (persist across restarts). This is a more robust failure mode than the previous hard-fail/restart cycle.

### 3. Per-identity skill libraries on shared Gateways (v2026.9.1)
Skills are scoped per user identity even when running on a shared Gateway (`openclaw skills library` with ZIP archive import and per-identity publishing controls). This separates skill discovery/authoring from deployment scope.

### 4. Gateway circuit-breaker / repair path (v2026.7.1)
Instead of restarting indefinitely on repeated failure, the Gateway now leaves a stable repair path. Implemented as a counted-restart circuit breaker: after N consecutive failures, it parks in a degraded/repairable state rather than continuing to thrash.

### 5. Guided multi-agent team orchestration (v2026.9.5)
Guided setup creates a four-agent team (chief-of-staff, researcher, writer, reviewer) via a proposal the user approves before agents are created. The roles are templates; the mechanism is agent-graph construction driven by a structured proposal flow — worth studying for Lexicon's orchestrator.

---

## What We Can Use in Lexicon

Ranked by value/effort (high value = strong signal / low effort = low implementation cost):

| # | Pattern | Value | Effort | Lexicon file |
|---|---------|-------|--------|-------------|
| 1 | **Cron quarantine on malformed jobs** — quarantine bad entries at load time, let scheduler boot, mark quarantined entries in store | High | Low | `src/cron/scheduler.py`, `src/cron/store.py` |
| 2 | **Cron one-shot retry persistence** — persist retry state so retries survive engine restart | High | Low | `src/cron/scheduler.py`, `src/cron/defaults.py` |
| 3 | **Gateway circuit-breaker** — counted restart limit → degrade to repair state instead of thrashing | High | Medium | `src/gateway/server.py` |
| 4 | **Tool/skill hot-reload** — reload `src/engine/skills.py` and `src/engine/tools/registry.py` without restarting the engine; drain in-flight calls before swapping the registry | High | Medium | `src/engine/skills.py`, `src/engine/tools/registry.py` |
| 5 | **Per-identity skill scoping** — scope loaded skills by session/identity context on shared runtime | Medium | Medium | `src/engine/skills.py`, `src/engine/workspace.py` |
| 6 | **Memory pressure ordering** — explicit OOM victim priority (drop working memory before episodic, episodic before LLM provider cache) | Medium | Low | `src/engine/memory/manager.py` |
| 7 | **Multi-agent team templates** — pre-defined role graphs (researcher + writer + reviewer) as a first-class orchestrator primitive | Medium | High | `src/engine/orchestrator.py` |

---

## Spike Picks

**Spike 1 — Cron quarantine + retry persistence** (`src/cron/scheduler.py`)  
Lowest effort, highest Lexicon payoff. A bad cron entry today can prevent scheduler boot entirely. Quarantine-on-load + persisted one-shot retry state addresses two known fragility points in a single pass. Start by adding a `quarantined` state to `src/cron/store.py` and wrapping the job-load loop in `scheduler.py` with try/except that writes to it.

**Spike 2 — Gateway circuit-breaker** (`src/gateway/server.py`)  
The current server restarts on any fatal error. A simple counted-restart limit (e.g., 5 within 60 s → enter `REPAIR` state, stop restart loop, emit a structured error event) mirrors what OpenClaw shipped in v2026.7.1 and is a one-file change.

**Spike 3 — Skill hot-reload** (`src/engine/skills.py` + `src/engine/tools/registry.py`)  
Worth a design spike before implementation. The core question is how to drain in-flight tool calls before swapping the registry — OpenClaw's approach (hold inbound registry stable, only swap execution path) is a concrete starting point.
