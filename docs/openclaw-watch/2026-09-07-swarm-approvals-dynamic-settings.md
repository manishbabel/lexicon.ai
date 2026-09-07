# OpenClaw Watch — 2026-09-07

**Versions covered:** 2026.8.1 · 2026.8.2 (Sep 1) · 2026.9.1 (Sep 3) · 2026.9.2 (Sep 5)
**Previous baseline:** 2026.5.27 (stable) / 2026.5.28-beta.2
**Source:** github.com/openclaw/openclaw/releases

---

## What shipped

| Version | Date | Headline |
|---------|------|----------|
| 2026.8.1 | Aug 2026 | Reliability fixes (details sparse in release notes) |
| 2026.8.2 | Sep 1 | Home agent sidebar; Linux `.deb`/AppImage; background sessions; voice reliability |
| 2026.9.1 | Sep 3 | Personal skill libraries on shared Gateways; Mermaid rendering; Codex approvals (durable tool perms); Gateway startup resilience |
| 2026.9.2 | Sep 5 | Swarm concurrent sub-agents on by default; GPT-6 Astra support; dynamic settings (no restart needed); restart-resilient reply recovery |

Four releases in ~10 days. Architecture-significant changes are concentrated in 2026.9.1–2 and are worth reviewing as a pair.

---

## What's notable

### 1. Swarm — parallel sub-agent orchestration (2026.9.2)
OpenClaw now enables **Swarm by default**: a top-level agent can fan out multiple sub-agent invocations concurrently, collecting results when they all settle. Prior to this, sub-agents were dispatched serially within a session lane. The pattern is `asyncio.gather`-style fan-out gated by a semaphore, with structured result collection back to the chief.

### 2. Codex approvals — durable per-tool permission grants (2026.9.1)
A runtime tool-permission layer that persists approval decisions across Gateway restarts. When a tool requires confirmation, approval is stored and replayed on restart — users don't re-approve on every boot. This is separate from the static allowlist: it handles *runtime* approval for tools the allowlist permits but that may be destructive.

### 3. Dynamic settings — hot config reload without restart (2026.9.2)
A meaningful set of settings now apply live without restarting the Gateway process. OpenClaw watches `config.json` for changes and reinitializes the affected subsystems (LLM provider, log level, etc.) in-place. Signal-triggered or file-watcher triggered.

### 4. Personal skill libraries on shared Gateways (2026.9.1)
Per-user skill overrides isolated from the Gateway's shared skill tree. Even when many users share one Gateway process, each user can install, override, and manage their own skills without affecting others. Scoped by a user identity key resolved at request time.

### 5. Background sessions (2026.8.2)
Sessions can be created and run in the background without interrupting the active foreground session. Background sessions use a separate queue lane and don't compete with foreground I/O. This is distinct from the cron lane — it's user-initiated, not schedule-triggered.

---

## What we can use in Lexicon

Ranked by estimated value ÷ effort. All file paths verified to exist in the repo.

### 1. Swarm concurrent sub-agents — HIGH value / MEDIUM effort
**OpenClaw pattern:** Fan out multiple sub-agent calls in parallel via `asyncio.gather` + semaphore.
**Lexicon gap:** `src/engine/orchestrator.py` exposes `MAX_CONCURRENT_SUBAGENTS = 4` and tracks `_active_runs`, but `route_to_agent` is called serially — callers cannot fire multiple sub-agents concurrently within a single chief turn.
**What to build:** Add a `route_many(tasks: list[dict]) -> list[str]` entry point on `Orchestrator` that uses `asyncio.gather(*[self.route_to_agent(**t) for t in tasks])` gated by an `asyncio.Semaphore(MAX_CONCURRENT_SUBAGENTS)`. Wire it as a new tool on the Chief so it can explicitly opt into fan-out.

### 2. Dynamic config reload — HIGH value / LOW effort
**OpenClaw pattern:** SIGHUP or file-watcher triggers `Settings` re-initialization without process restart.
**Lexicon gap:** `src/shared/config.py` loads `Settings` once at startup; changing API keys or log level requires a full Gateway restart.
**What to build:** Add a `reload()` classmethod to `Settings` (or a module-level `get_settings()` accessor returning a cached singleton), and register a `SIGHUP` handler in `src/gateway/server.py` that calls `reload()` and re-wires the LLM router in `src/engine/llm/router.py`.

### 3. Durable tool permissions (Codex approvals pattern) — HIGH value / HIGH effort
**OpenClaw pattern:** Runtime approval decisions stored and replayed across restarts; separate from the static allowlist.
**Lexicon gap:** `src/engine/registry.py` has a static `AGENT_TOOL_ALLOWLIST`; `src/engine/tools/registry.py` has no runtime approval flow.
**What to build:** A `ToolApprovalStore` (JSONL, similar to `src/cron/store.py`) keyed by `(agent_id, tool_name)` → `approved | denied | pending`. Integrate into `Orchestrator._wire_tools()` as a pre-filter. The Chief's `route_to_agent` tool becomes the approval request surface for sub-agents.

### 4. Personal skill libraries on shared Gateways — MEDIUM value / MEDIUM effort
**OpenClaw pattern:** User-identity-scoped Tier 3 skills that don't bleed across users on a shared process.
**Lexicon gap:** `src/engine/skills.py` `SkillRegistry.load_all()` loads a single Tier 3 path (`WORKSPACES_DIR / persona / "skills"`), shared for all sessions of that persona regardless of which user is connected.
**What to build:** Pass a `user_id` into `load_all()` and add a Tier 4 path `~/.lexicon/users/<user_id>/skills/` that wins over Tier 3. The `src/gateway/session.py` session object already carries per-connection context where `user_id` could be resolved.

### 5. Background sessions — MEDIUM value / MEDIUM effort
**OpenClaw pattern:** User-initiated sessions that run in a non-interrupting background lane.
**Lexicon gap:** `src/engine/queue.py` has a cron lane for scheduled work and a main lane for interactive sessions, but no user-triggered background lane.
**What to build:** Add a `background` lane in `src/engine/queue.py` (concurrency cap separate from `main`) and a `create_background_session` API on `src/gateway/server.py` that enqueues into that lane.

---

## My picks for what to spike next

1. **Dynamic config reload** — one-session spike, high daily-use payoff. Start with the SIGHUP handler in `src/gateway/server.py` + a `get_settings()` accessor in `src/shared/config.py`. No new abstractions required.

2. **Swarm concurrent sub-agents** — the `route_many` tool on `Orchestrator` is ~40 lines and immediately enables parallel research workflows (e.g., Chief asks software-engineer + ai-educator simultaneously). Test with the existing `MAX_CONCURRENT_SUBAGENTS` semaphore gate.

3. **Durable tool permissions** — design first, implement second. The `ToolApprovalStore` needs a clear API contract before touching `Orchestrator._wire_tools()`.
