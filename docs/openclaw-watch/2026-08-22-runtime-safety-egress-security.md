# OpenClaw Watch — 2026-08-22: Runtime Safety & Egress Security

**Baseline:** 2026.5.27 (stable) / 2026.5.28-beta.2 (beta)
**Checked:** 2026-08-22

---

## What Shipped

### Stable track

| Version | Date | Headline |
|---|---|---|
| 2026.7.1-1 | Aug 4, 2026 | Memory Core startup conflict recovery; WSL state permission tolerance |
| 2026.7.1-2 | Aug 4, 2026 | npm plugin singleton-array metadata fix for official plugin updates |
| 2026.6.34 | Aug 8, 2026 | Extended-stable maintenance: safer browser/network boundaries, agent/provider run resilience, SQLite checkpoint hardening, channel recovery with pending-work resumption |

**Latest stable: 2026.7.1-2**

### Beta track

| Version | Date | Headline |
|---|---|---|
| 2026.7.2-beta.6 | Aug 1, 2026 | State safety, channel delivery durability, structured approvals with push notifications |
| 2026.7.2-beta.7 | Aug 2, 2026 | Quarantine stores, crash-recoverable SQLite snapshots, session rewind + branching, durable channel delivery across 9 platforms |
| 2026.8.1-beta.2 | Aug 15, 2026 | Secret egress host binding, atomic model/runtime switching, SQLite snapshot backup/restore, macOS app instance isolation, plugin install provenance warnings, channel ingress monitors |

**Latest beta: 2026.8.1-beta.2**

---

## What's Notable

### 1. Secret egress host binding
Shared-store secrets are now bound to specific HTTPS destination hosts at write time. Any attempt to send a bound secret to a different host is rejected at the runtime boundary. This prevents a class of secret exfiltration bugs where a misconfigured or hijacked tool sends credentials to an attacker-controlled endpoint.

### 2. Crash-recoverable SQLite snapshots with quarantine stores
The agent runtime now writes state to a quarantine store before committing; on crash recovery the snapshot is verified before promotion, and corrupted states are quarantined rather than causing fatal loops. Combined with the 2026.6.34 SQLite checkpoint hardening, this is a complete write-safety story for the memory layer.

### 3. Memory Core startup conflict recovery (no fatal restart loops)
The memory subsystem now detects index-vs-cache conflicts at startup and self-repairs rather than entering a fatal restart loop. This was a reliability gap: a single corrupt index could make the whole agent unresponsive.

### 4. Atomic model/runtime switching
LLM provider and runtime engine can now be swapped atomically without dropping in-flight requests. In-progress tool calls drain before the switch commits. This unlocks hot-reloading model configs and graceful fallbacks without a full restart.

### 5. Durable channel delivery with pending-work resumption
Channels now persist undelivered outbound messages and retry delivery after reconnect. The gateway no longer drops pending writes on network interruption.

---

## What We Can Use in Lexicon

Ranked by value/effort. All file paths verified to exist.

| # | Pattern | Value | Effort | Target file(s) |
|---|---|---|---|---|
| 1 | Memory Core startup conflict recovery | High | Low | `src/engine/memory/manager.py` |
| 2 | Crash-recoverable SQLite snapshots + quarantine stores | High | Medium | `src/engine/memory/manager.py`, `src/engine/memory/episodic.py` |
| 3 | Secret egress host binding | High | Medium | `src/vault/writer.py`, `src/vault/reader.py` |
| 4 | Atomic model/runtime switching | Medium | Medium | `src/engine/llm/router.py` |
| 5 | Durable channel delivery / pending-work resumption | Medium | Medium | `src/gateway/session.py`, `src/gateway/router.py` |
| 6 | Plugin install provenance warnings | Low | Low | `src/engine/hooks/registry.py` |
| 7 | Session rewind + branching | Medium | High | `src/engine/memory/transcript_index.py`, `src/engine/memory/episodic.py` |

---

## My Picks for Next Spike

**Spike 1 (do this week): Memory Core startup recovery** — `src/engine/memory/manager.py`
Low effort, high value. Add index-vs-cache conflict detection at manager init and a self-repair path (rebuild index from episodic store) before surfacing a fatal error. Mirrors what OpenClaw calls "Memory Core startup repairs." Prevents the class of fatal restart loops we've seen intermittently in staging.

**Spike 2 (this sprint): Crash-recoverable snapshots** — `src/engine/memory/manager.py`, `src/engine/memory/episodic.py`
Write a quarantine-then-commit wrapper around the episodic and working memory persistence paths. Snapshot before each write, verify on load, quarantine corrupt states with a timestamp. Medium effort but eliminates the most common support escalation (corrupt memory state requiring manual wipe).

**Spike 3 (next sprint): Secret egress host binding** — `src/vault/writer.py`, `src/vault/reader.py`
Attach an optional `allowed_hosts` set to each vault entry at write time. Enforce at read time in `vault/reader.py` by comparing the caller-supplied destination host against the bound set. Low-friction security win that closes a real threat model gap.
