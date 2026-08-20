# OpenClaw Watch — August 2026: State Safety & Durable Delivery

**Date:** 2026-08-20  
**Baseline:** stable `2026.5.27` / beta `2026.5.28-beta.2`  
**New stable:** `2026.7.1-2` (2026-08-04)  
**New beta:** `2026.8.1-beta.2` (2026-08-15)

---

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.6.1 | Jun 2026 | stable | SQLite storage migration (cron, inbound queues, ACP metadata) |
| 2026.6.34 | 2026-08-08 | extended-stable | Security/reliability maintenance: safer network boundaries, resilient agent/provider runs |
| 2026.7.1-1 | 2026-08-04 | stable | Memory Core startup repair, WSL state permissions, legacy migration recovery |
| 2026.7.1-2 | 2026-08-04 | stable | npm plugin update compatibility for official plugins |
| 2026.7.2-beta.6 | 2026-08-01 | beta | State safety, crash-recoverable SQLite snapshots |
| 2026.7.2-beta.7 | 2026-08-02 | beta | Quarantine stores, durable channel delivery, session rewind/branching, structured approvals |
| 2026.8.1-beta.2 | 2026-08-15 | beta | Secret egress host binding, SQLite snapshot backup CLI, plugin install provenance |

---

## What's Notable

### 1. SQLite replaces JSON/JSONL for all mutable runtime state (2026.6.1)

OpenClaw moved cron job definitions, inbound channel queues, and plugin ledgers from flat JSON files to SQLite. Cron migrations were designed backward-compatible with legacy run-log table shapes. The key driver: atomic writes and crash-safe reads — a full-rewrite of `jobs.json` can lose state mid-write; a SQLite `BEGIN/COMMIT` cannot.

### 2. Quarantine stores + crash-recoverable snapshots (2026.7.2-beta.7)

Primary-database damage no longer destroys agent state. OpenClaw isolates writes into a quarantine store (a secondary SQLite DB), promotes to primary only after a verified schema check, and maintains snapshot artifacts for rollback. Schema-upgrade data-loss is rejected before it runs. This creates a transaction boundary around the entire agent turn.

### 3. Durable channel delivery with dead-letter recovery (2026.7.2-beta.7)

Accepted inbound messages are now persisted to SQLite before dispatch, survive gateway restarts and local crashes via a shared ingress drain, and failed deliveries are routed to a dead-letter store for replay. Covers Telegram, Slack, Signal, IRC, and others. Previously, a gateway crash between message receipt and agent dispatch silently dropped the message.

### 4. Plugin install provenance enforcement (2026.8.1-beta.2)

Arbitrary-source plugin installs (non-ClawHub, non-official-catalog) now require an explicit `--force` acknowledgment at install time. Trusted flows (ClawHub, bundled, official catalog, tracked-update) remain frictionless. A shared plugin SDK monitor handles admission, claim-identity validation, and handoff. The security model shifts from "install anything unless blocked" to "trust is opt-in for unknown sources."

### 5. Secret egress host binding (2026.8.1-beta.2)

Shared-store secrets are now bound to exact HTTPS destination hosts. Unbound secrets fail closed before plaintext egress across CLI, gateway RPC, and control UI. Previously, a secret loaded into the agent context could be forwarded to any outbound URL — this adds an allowlist enforcement layer at the point of transmission.

---

## What We Can Use in Lexicon

Ranked by value/effort (highest value first within each effort tier).

### High value / Low effort

**1. SQLite-backed cron store** → `src/cron/store.py`

The current store does a full JSON rewrite on every `save()` call (line 122–127). A partial write or process crash between `write_text()` and `flush` corrupts the entire jobs file. The OpenClaw 2026.6.1 pattern replaces this with a SQLite table: one row per job, atomic `INSERT OR REPLACE`, no full-file rewrites. Migration is straightforward since `CronJob` maps cleanly to a flat table. Effort: ~1 day. Risk: low (no API surface change, same `CronJobStore` interface).

**2. Skill/tool source provenance** → `src/engine/skills.py` + `src/engine/tools/registry.py`

Skills currently load from three tiers of directories with no verification of where a SKILL.md came from (line 8–12 of `skills.py`). The OpenClaw provenance model is directly portable: tag each discovered skill with its source tier and, for user-installed skills (`~/.lexicon/skills/`), require an explicit trust acknowledgment on first load. Effort: ~0.5 days. Risk: low.

### High value / Medium effort

**3. Durable gateway message delivery** → `src/gateway/session.py` + `src/gateway/router.py`

`SessionManager` dispatches agent runs via the command queue lane (session.py line 20). If the gateway process dies between message receipt and queue write, the message is lost. The OpenClaw pattern: write the inbound message to a SQLite ingress table first, then dispatch; on startup, drain the ingress table for any unprocessed messages. Effort: ~2 days (needs a new ingress store + drain loop in `router.py`). Risk: medium (touches the hot path).

**4. Memory layer durability (short-term + episodic)** → `src/engine/memory/episodic.py` + `src/engine/memory/short_term.py`

Both currently use JSONL append — no crash-safe writes, no easy point-in-time snapshots. The quarantine store pattern from 2026.7.2-beta.7 applies: write to a shadow JSONL, fsync, then atomically rename over the primary. Alternatively, migrate to SQLite rows (consistent with cron store spike above). Effort: ~2 days. Risk: medium.

### Medium value / Low effort

**5. Egress host binding for secrets** → `src/shared/config.py`

Lexicon loads API keys and tokens via `shared/config.py`. There is no enforcement that a secret is only sent to its intended host. Add an `allowed_hosts` field per secret entry and a validation check in the LLM provider layer (`src/engine/llm/provider.py`) before any outbound call. Effort: ~0.5 days. Risk: low.

---

## My Picks to Spike Next

1. **SQLite cron store** (`src/cron/store.py`) — proven in OpenClaw stable since June, direct drop-in, removes the most concrete data-loss risk we have today. Spike it in isolation with a schema migration util and keep the `CronJobStore` interface unchanged.

2. **Skill provenance tagging** (`src/engine/skills.py`) — small change, meaningful for the three-tier model: mark user-installed skills explicitly and surface the source in the system prompt listing so the agent (and the user) can see trust level at a glance.

---

*Sources: [OpenClaw releases page](https://github.com/openclaw/openclaw/releases) · [2026.7.2-beta.7 notes](https://github.com/openclaw/openclaw/releases/tag/v2026.7.2-beta.7) · [2026.8.1-beta.2 notes](https://github.com/openclaw/openclaw/releases/tag/v2026.8.1-beta.2) · [SEN-X coverage](https://senx.ai/openclaw-news/2026-08-02-openclaw-news)*
