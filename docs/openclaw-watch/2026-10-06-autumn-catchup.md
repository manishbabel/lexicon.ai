# OpenClaw Digest: 2026-10-06 Autumn Catch-up

**Baseline**: stable 2026.5.27 / beta 2026.5.28-beta.2  
**Now**: stable 2026.9.7 / LTS 2026.9.8 / beta 2026.10.1-beta.1  
**Checked**: 2026-10-06

---

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| 2026.9.3 | ~Aug 2026 | Stable | Bounded candidate validation for safer updates |
| 2026.9.6 | Sep 23 2026 | Stable | 178 commits, 2 614 PRs; macOS crash hotfix rebuild Sep 24 |
| 2026.9.7 | Sep 30 2026 | Stable | 518 commits, 2 818 PRs; update-safety DB snapshots; OpenAI Agents API + ChatGPT sign-in (beta) |
| 2026.8.33 | Sep 29 2026 | LTS | Meta Muse Spark 1.3, Fable 5.1, GPT-6 Astra; Prometheus auth hardening |
| 2026.8.34 | Oct 2 2026 | LTS | 113 audit-selected fixes; credential/agent-state preservation through upgrades |
| 2026.8.35 | Oct 2 2026 | LTS | GPT-6.1 Sol routing; plugin-settings preservation; agent-completion reliability |
| 2026.9.8 | Oct 3 2026 | LTS | 58 commits / 43 PRs; stability-only; designated extended-stable |
| 2026.10.1-beta.1 | Oct 5 2026 | Beta | Embedding-cache bounded batch migration; registry-change preservation; gateway config-probe opt |

---

## What's Notable

### 1. Update-safety: snapshot-then-migrate (2026.9.7)
Before any schema migration, OpenClaw now snapshots every state and agent database while the Gateway keeps writing (consistent snapshot under live I/O). If post-migration rollback is triggered — or if snapshot cleanup itself fails — the restore fires automatically. The migration pipeline stops before touching schema when the cleanup step reports an error.

**Why it matters**: production deployments that were losing memory state on crashed upgrades now have a deterministic recovery path. The pattern applies to any persistent store that evolves with the binary.

### 2. Isolated candidate-state validation for live updates (2026.9.3)
Update rehearsal runs in a disposable copy of agent state before the real activation. If validation fails, the candidate can enter a bounded self-repair phase using configured inference, with operator-visible report on unresolvable diffs. Only clean candidates activate.

**Why it matters**: safe hot-reload of config / plugin changes without touching production state. The rehearsal-then-swap pattern is directly portable to cron job reconfiguration.

### 3. Embedding-cache bounded batch migration (2026.10.1-beta.1)
Embedding index migrations now run in bounded batches rather than a single blocking pass. Registry change events are preserved across restarts so a partial migration resumes correctly rather than restarting from scratch. Gateway config probing is deferred until after the first healthy agent session, cutting startup time.

**Why it matters**: avoids the full-rebuild penalty on vector index schema changes and makes Lexicon's embedding-backed search restartable mid-migration.

### 4. OpenAI Agents API + ChatGPT sign-in (2026.9.7 beta feature)
New provider integration using OpenAI's Agents API endpoint and device-code OAuth for ChatGPT. Routing and discovery systems updated to surface Agents-API models alongside standard completions.

**Why it matters**: Agents API exposes tool-use and handoff primitives at the provider level, reducing framework-side orchestration overhead.

### 5. Prometheus metrics authorization hardening (2026.8.33)
Metrics endpoint now requires an authorization token; scrape config updated accordingly. Pairs with broader command-parsing security audit in the same LTS rollup (browser origin checks, credential boundary tightening in remote-filesystem mutation).

**Why it matters**: metrics endpoints are often left open unintentionally; this is a one-file gateway patch with a clear security return.

---

## What We Can Use in Lexicon

Ranked by value / effort (lower = cheaper):

| # | Pattern | Effort | Value | Lexicon files |
|---|---|---|---|---|
| 1 | Snapshot-before-migration on memory stores | Medium | High | `src/engine/registry.py`, `src/engine/memory/manager.py` |
| 2 | Bounded batch migration for embedding index rebuilds | Medium | High | `src/engine/memory/search.py`, `src/engine/memory/transcript_index.py` |
| 3 | Isolated rehearsal state for cron job hot-reload | Low–Medium | Medium | `src/cron/scheduler.py`, `src/cron/store.py` |
| 4 | Agents API provider adapter | Low | Medium | `src/engine/llm/openai_provider.py`, `src/engine/llm/router.py` |
| 5 | Auth guard on metrics / introspection endpoints | Low | Medium | `src/gateway/server.py` |

**Detail on top two picks:**

**#1 — Snapshot-before-migration** (`src/engine/registry.py`, `src/engine/memory/manager.py`):  
`MemoryManager` writes to short-term JSONL and episodic JSONL stores. Today there is no snapshot step before structural changes (e.g. adding a new memory field). Port the pattern: before any migration in `manager.py`, write a `.bak` copy of the affected JSONL files; wrap the migration in a try/except that restores from `.bak` on failure. `src/engine/registry.py` is the right place to track migration version and gate writes.

**#2 — Bounded embedding migration** (`src/engine/memory/search.py`, `src/engine/memory/transcript_index.py`):  
`TranscriptIndex` rebuilds on schema change. Make it resumable: persist a `migration_cursor` in `src/cron/store.py`, process N documents per scheduler tick, and mark complete when cursor reaches end. Avoids the blocking full-rebuild on restart.

---

## My Picks for Next Spike

1. **Bounded embedding migration** — lowest setup cost, directly unblocks `TranscriptIndex` reliability on restarts. `src/engine/memory/transcript_index.py` + `src/cron/store.py`.
2. **Snapshot-before-migration** — higher effort but the safety return is large if Lexicon ever ships to non-dev environments. `src/engine/registry.py` first.
