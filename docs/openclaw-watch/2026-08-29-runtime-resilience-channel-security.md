# OpenClaw Watch: 2026-08-29 — Runtime Resilience & Channel Security

**Digest date:** 2026-08-29  
**Baseline:** stable 2026.5.27 / beta 2026.5.28-beta.2  
**Sources:** github.com/openclaw/openclaw/releases

---

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.7.1-2 | 2026-08-04 | **stable** | Plugin metadata singleton-array compatibility fix |
| 2026.8.1-beta.2 | 2026-08-15 | beta | Secret egress host binding; plugin provenance warnings; channel ingress monitors |
| 2026.8.1-beta.3 | 2026-08-24 | beta | External gateway lifecycle supervision; SQLite backup/restore; shared durable ingress monitors |
| 2026.9.1-beta.1 | 2026-08-28 | beta | Gateway restart recovery preserving admitted turns; worker re-arming on admission-deadline |

**Newest stable:** 2026.7.1-2 (minor compatibility fix — not architecturally notable on its own)  
**Newest beta:** 2026.9.1-beta.1

---

## What's Notable

### 1. Gateway restart recovery with turn preservation (2026.9.1-beta.1)
OpenClaw's gateway now checkpoints in-flight turns before restart and re-admits them after the new process is ready. The handoff is verified: the old process signals readiness-transfer, the new process confirms before the old one exits. Sessions survive gateway restarts without losing queued user input.

**Why it matters:** Lexicon's gateway (`src/gateway/server.py`, `src/gateway/session.py`) has no equivalent checkpoint — a restart drops any turn currently being routed. This is the same class of problem.

### 2. Shared durable ingress monitors for channel plugins (2026.8.1-beta.3 / 2026.9.1-beta.1)
Channel plugins can now register a named ingress monitor that survives plugin reload. Monitors are owned by the gateway process, not the plugin, so a plugin crash or hot-reload doesn't lose incoming events. Admission is tracked separately from delivery.

**Why it matters:** Lexicon routes channel traffic through `src/gateway/router.py` with no durable handoff layer; events during a skill reload are silently lost.

### 3. Plugin install provenance warnings (2026.8.1-beta.2)
OpenClaw now emits a structured warning (and requires explicit acknowledgment) when a plugin is installed from an unverified source. The provenance check compares a content hash against the registry manifest before execution.

**Why it matters:** Lexicon loads skills at runtime via `src/engine/skills.py` and `src/engine/tools/registry.py` with no integrity check on the loaded artifact.

### 4. Secret egress host binding (2026.8.1-beta.2)
OpenClaw can bind secrets to a named egress host allowlist, so a leaked credential can only reach its intended destination even if exfiltrated. Configured per-secret in the runtime config.

**Why it matters:** Lexicon stores credentials in `src/shared/config.py` with no egress scope — a credential exfiltrated from a tool call can reach any host.

### 5. SQLite backup/restore with compact verification (2026.8.1-beta.3)
The cron/state store now supports point-in-time backup and restore with a compact checksum verification step. Restore is atomic: the old DB is swapped only after the new one passes verification.

**Why it matters:** Lexicon's cron store (`src/cron/store.py`) has no backup path. A corrupt store means lost scheduled jobs.

---

## What We Can Use in Lexicon

Ranked by value-to-effort ratio. All file paths verified present in the repo.

| # | Pattern | Value | Effort | Lexicon target |
|---|---|---|---|---|
| 1 | **Plugin provenance check on skill load** | High | Low | `src/engine/skills.py`, `src/engine/tools/registry.py` — add hash verification at load time against a manifest; no new dependencies |
| 2 | **SQLite backup/restore for cron store** | High | Low | `src/cron/store.py` — add a `backup()` / `restore_from(path)` with checksum; minimal scope |
| 3 | **Gateway restart turn checkpoint** | High | Medium | `src/gateway/server.py` + `src/gateway/session.py` — write admitted turns to a temp file on SIGTERM, re-read on startup |
| 4 | **Durable ingress monitor for channel routing** | Medium | Medium | `src/gateway/router.py` — own the monitor at the gateway level, pass a delivery callback to skill plugins so a skill reload doesn't drop the subscription |
| 5 | **Secret egress host binding** | Medium | High | `src/shared/config.py` + `src/engine/llm/provider.py` — add an `egress_hosts` field per credential, enforce at LLM provider call time |

---

## Picks to Spike Next

**#1 — Plugin provenance check** (`src/engine/skills.py`): One function, no infrastructure. Add a `verify_skill_hash(path, manifest)` call before any dynamic skill load. We can ship this in a single PR and it closes a real supply-chain gap.

**#2 — Cron store backup** (`src/cron/store.py`): Add a scheduled backup job using the existing cron scheduler (`src/cron/scheduler.py`). Low-risk, self-contained, and protects scheduled job state across crashes.

Hold off on #3 (gateway checkpoint) until the gateway session lifecycle is better understood — the right place to write the checkpoint (before SIGTERM vs. after last turn drains) needs a closer read of `src/gateway/session.py` and `src/gateway/server.py` together.
