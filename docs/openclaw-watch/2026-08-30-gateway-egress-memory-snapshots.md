# OpenClaw Watch — 2026-08-30

## What Shipped

Three beta releases since baseline (2026.5.27 stable / 2026.5.28-beta.2 beta), plus one stable hotfix not covered here.

| Version | Date | Headline |
|---|---|---|
| **2026.9.1-beta.1** | Aug 28, 2026 | Gateway restart recovery preserving admitted turns; Codex 0.150.1 |
| **2026.8.1-beta.3** | Aug 24, 2026 | SQLite backup/restore; external gateway lifecycle supervision; CDP relay; GPT-5.6 Sol/Terra/Luna/Ultra |
| **2026.8.1-beta.2** | Aug 15, 2026 | Secret egress host binding; shared channel ingress monitors; SQLite snapshots; plugin provenance warnings |
| 2026.7.1-2 | Aug 4, 2026 | Hotfix: npm plugin singleton-array metadata fix — skipped (no porting value) |

Newest stable: **2026.7.1-2** · Newest beta: **2026.9.1-beta.1**

---

## What's Notable

### 1. Gateway turn preservation across restarts (2026.9.1-beta.1)
OpenClaw now checkpoints admitted (in-flight) turns at the gateway layer so a supervisor restart doesn't lose the client's session state. The pattern is: turns are serialised to a lightweight store on admission and cleared on completion, not on disconnect.

### 2. Secret egress host binding (2026.8.1-beta.2)
Outbound LLM/tool calls are bound to an explicit allowlist of egress hosts declared in config. Calls to any unlisted host are rejected before the TCP handshake. Positioned as a security primitive — prevents a compromised skill/plugin from exfiltrating data through arbitrary endpoints.

### 3. Shared channel ingress monitors (2026.8.1-beta.2)
Gateway channel plugins now expose a monitor hook that fires on every incoming message before routing. OpenClaw uses it for rate-limiting and audit logging without coupling those concerns into the routing layer.

### 4. SQLite snapshot + backup/restore for memory (2026.8.1-beta.2 → beta.3)
Episodic memory can now be snapshotted to a named backup (hot copy, no lock required) and restored on startup from a snapshot. This enables point-in-time agent memory recovery after a crash, and is the foundation for cross-instance memory sharing.

### 5. Plugin install provenance warnings (2026.8.1-beta.2)
The plugin loader now reads a `provenance` field from skill/tool manifests. Unsigned or untrusted-source installs surface a blocking warning requiring explicit acknowledgment. The pattern separates trust tiers at load time rather than at runtime capability-grant time.

---

## What We Can Use in Lexicon

Ranked by value/effort. Each path is verified to exist in this repo.

### 1. Secret egress allowlist · `src/shared/config.py` + `src/gateway/server.py`
**Value: High / Effort: Low**
Add an `egress_allow` list to Lexicon's config and enforce it at the gateway's outbound call boundary. Lexicon tools like `src/engine/tools/web_search.py` and `src/engine/tools/paper_fetch.py` make arbitrary outbound calls today with no host restriction. A simple allowlist check in the gateway or a shared middleware stops lateral exfiltration from a compromised tool. Minimal change, meaningful security posture improvement.

### 2. Gateway turn checkpointing · `src/gateway/session.py` + `src/gateway/server.py`
**Value: High / Effort: Medium**
`src/gateway/session.py` tracks per-session state but does not persist it. Adding a checkpoint-on-admission / clear-on-completion pattern means that when `src/gateway/server.py` restarts (e.g. under a process supervisor), in-flight sessions can be resumed rather than dropped. The engine queue in `src/engine/queue.py` already tracks pending work — the gap is serialising that across the gateway boundary.

### 3. Memory snapshots · `src/engine/memory/manager.py` + `src/engine/memory/episodic.py`
**Value: High / Effort: Medium**
`src/engine/memory/episodic.py` writes to a store that has no snapshot mechanism. Adding a hot-copy snapshot (trigger via cron in `src/cron/scheduler.py`) and a startup restore path in `src/engine/memory/manager.py` enables point-in-time recovery for long-running agents without downtime. SQLite's backup API is a one-liner; the integration work is in restore ordering relative to `src/engine/memory/working.py` hydration.

### 4. Tool/hook provenance check · `src/engine/hooks/loader.py` + `src/engine/tools/setup.py`
**Value: Medium / Effort: Low**
`src/engine/hooks/loader.py` loads hooks dynamically without any trust tier. Adding a `provenance` field to skill/tool manifests and a warn-or-block policy in the loader mirrors OpenClaw's pattern. `src/engine/tools/setup.py` is a natural place to enforce this at install time, complementing the runtime check.

### 5. Channel ingress monitor hook · `src/gateway/router.py` + `src/gateway/protocol.py`
**Value: Medium / Effort: Medium**
`src/gateway/router.py` handles dispatch but has no pre-route hook for cross-cutting concerns (rate limits, audit). Adding a monitor registration similar to OpenClaw's ingress hook — a small list of callables consulted before routing — decouples audit/rate-limit logic from the router core and makes it testable in isolation.

---

## My Picks to Spike Next

1. **Egress allowlist** (`src/shared/config.py` + `src/gateway/server.py`) — highest leverage for the least code. One config field and one check in the outbound call path. Spike: add `egress_allow: list[str]` to config, enforce in `src/gateway/server.py` before forwarding; test with a blocked domain returning a clean error.

2. **Memory snapshots** (`src/engine/memory/manager.py`) — long-running agent reliability with no user-visible API change. Spike: wire SQLite's `backup()` into a nightly cron job in `src/cron/scheduler.py`, add `--restore-snapshot <path>` to the startup path in `src/engine/memory/manager.py`.
