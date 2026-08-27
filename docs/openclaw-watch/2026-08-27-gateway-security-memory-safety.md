# OpenClaw Watch — 2026-08-27

## What Shipped

**Stable track**

| Version | Released | Headline |
|---|---|---|
| 2026.7.1-2 | Aug 4, 2026 | npm plugin metadata compatibility; managed plugin update recovery |
| 2026.7.1-1 | Aug 4, 2026 | Memory Core startup repair; WSL state permission fix; Codex progress replies restored |
| 2026.6.34 | Aug 8, 2026 | Extended-stable: hardened browser/network boundaries; idempotent channel acks; SQLite + workspace state robustness |

**Beta track**

| Version | Released | Headline |
|---|---|---|
| 2026.8.1-beta.3 | Aug 24, 2026 | GPT-5.6 (Sol/Terra/Luna/Ultra) reasoning support; CDP relay; Gateway lifecycle supervision; SQLite backup/restore |
| 2026.8.1-beta.2 | Aug 15, 2026 | Secret egress host binding; shared ingress monitors; macOS app profiles; Control UI update recovery |
| 2026.7.2-beta.7 | Aug 2, 2026 | Quarantine store; crash-recoverable snapshots; session rewind/branching; interactive MCP dashboards; meetings integration |

All versions are newer than our baseline (stable 2026.5.27 / beta 2026.5.28-beta.2).

---

## What's Notable

**1. Secret egress host binding** (`2026.8.1-beta.2`)
Each secret stored in the shared store is bound to an exact HTTPS destination host at write time. At call time the runtime rejects any request where the resolved host does not match the binding — enforced in CLI, Gateway RPC, and Control UI. This closes a class of SSRF and credential-leakage bugs where a compromised tool or prompt could redirect a bearer token to an attacker-controlled host.

**2. Crash-recoverable memory snapshots + quarantine store** (`2026.7.2-beta.7`)
Working and episodic memory now checkpoint to a compact snapshot file on every write. On startup the runtime detects a dirty snapshot, moves the corrupted segment to a quarantine store (preserved for inspection), and recovers from the last clean checkpoint. Prevents silent data loss after ungraceful shutdown.

**3. Gateway lifecycle supervision with verified restart handoff** (`2026.8.1-beta.3`)
The external supervisor tracks Gateway PID and health endpoint. On restart it waits for the health check to return green before handing off active sessions — no more dropped WebSocket connections from race conditions during hot reload or crash recovery.

**4. Idempotent channel acknowledgements** (`2026.6.34`)
Channel plugins now stamp outbound messages with a monotonic sequence ID; the receiver deduplicates on replay. Prevents double-delivery when a connection drops mid-send and the client retries.

**5. SQLite verified backup/restore** (`2026.8.1-beta.3`)
`openclaw backup sqlite create|list|verify|restore` — compact artifacts with built-in integrity verification and fresh-target restore. Useful operational primitive for zero-downtime migrations and disaster recovery.

---

## What We Can Use in Lexicon

Ranked by value/effort. Every file path verified to exist in this repo.

| # | Pattern | Value | Effort | Lexicon target |
|---|---|---|---|---|
| 1 | **Secret egress host binding** | High | Low | `src/engine/llm/router.py`, `src/engine/tools/web_search.py` |
| 2 | **Crash-recoverable memory snapshots** | High | Medium | `src/engine/memory/manager.py`, `src/engine/memory/working.py` |
| 3 | **Idempotent channel acks** | Medium | Low | `src/gateway/session.py` |
| 4 | **Gateway restart handoff** | Medium | Medium | `src/gateway/server.py` |
| 5 | **SQLite verified backup** | Low | Low | `src/feedback/db.py` |

**Secret egress host binding** — `src/engine/llm/router.py` resolves which provider+model a persona uses and constructs the outbound request. Adding a host allowlist check here (resolved URL host must match a per-provider binding stored alongside the API key) would prevent any tool or prompt injection from redirecting LLM credentials to an unregistered host. `src/engine/tools/web_search.py` needs the same treatment for search API keys.

**Crash-recoverable memory snapshots** — `src/engine/memory/manager.py` is the unified store/recall surface. `src/engine/memory/working.py` holds the in-process deque. A lightweight pattern: on every write to working memory, atomically rename a JSON snapshot file (write-to-temp then rename). On MemoryManager `__init__`, detect a dirty snapshot, move it aside, and reload from the last clean one. The quarantine side is just a dated copy — no complex store needed.

**Idempotent channel acks** — `src/gateway/session.py` manages the per-session WebSocket lifecycle. Stamping outbound messages with a session-scoped sequence counter and checking for replays on inbound acks is a small addition with meaningful resilience benefit when connections drop.

---

## My Picks for What to Spike Next

1. **Secret egress host binding** — immediate security value, narrow scope. Start with `src/engine/llm/router.py`: add a `_assert_host_allowed(url, provider)` guard called before every provider dispatch. Can ship independently with no behaviour change for correctly-configured installations.

2. **Crash-recoverable memory snapshots** — the current `src/engine/memory/working.py` deque has no persistence path; losing a session to a crash drops all working context. The atomic-rename snapshot pattern is low-risk and high return.

3. **Idempotent channel acks** — quick win in `src/gateway/session.py`. Pairs well with any future work on reconnection logic.
