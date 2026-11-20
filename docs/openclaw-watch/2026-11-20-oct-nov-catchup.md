# OpenClaw Watch — 2026-11-20 Catchup Digest

Coverage: 2026.5.27 → **2026.11.6** (stable) / **2026.11.10-beta.1** (beta)  
Prior check: 2026-09-23  
Sources: github.com/openclaw/openclaw/releases

---

## What shipped

### Stable

| Version | Date | Headline |
|---|---|---|
| 2026.10.33 | ~2026-11-18 | "Extended-stable" / LTS build; on-demand skill search; MCP-event automations; bounded session stores; major security hardening |
| 2026.11.3 | ~2026-11-15 | Incremental; details not public |
| 2026.11.4 | 2026-11-16 | Incremental (220 commits, 125 PRs) |
| 2026.11.5 | 2026-11-17 | Incremental (11,811 commits total, large release) |
| **2026.11.6** | 2026-11-19 | **Latest** — 406 commits, 386 PRs, 157 contributors; npm + ClawHub published |

Earlier 2026 stables skipped (2026.6–2026.9) are routine dep/UI bumps with no architecture signal.

### Beta

| Version | Date | Headline |
|---|---|---|
| 2026.11.5-beta.2–4 | 2026-11-14–16 | Telegram widgets, provider recovery, DB backup fixes |
| **2026.11.10-beta.1** | 2026-11-19 | **Latest beta** — agent templates from ClawHub packages; copy-and-swap state migration; usage-ranked tool index |

---

## What's notable

### 1. On-demand skill loading (2026.10.33)

Installed skills are indexed by metadata and loaded only when relevant to the current task. The full skill content goes into the prompt only when matched — not every skill, every turn. This is a direct solution to prompt-bloat as skill libraries grow.

### 2. MCP-event and polled-condition automations (2026.10.33)

Automations can now trigger on polled conditions and MCP events, not only on schedule. Each automation is scoped to an explicit allowlist of MCP servers. This is OpenClaw's answer to agentic scheduling that reacts to external state rather than just a clock.

### 3. Bounded session stores + credential redaction in compaction (2026.10.33)

Memory export, indexing, and transcript trimming are bounded to avoid OOM on long conversations. Separately, compaction now redacts credentials inside quoted summaries — previously the compactor could echo secrets from earlier turns into the compressed context.

### 4. Copy-and-swap state migration (2026.11.10-beta.1)

Gateway state is rebuilt beside the live store at startup, then swapped atomically. The live store is never modified in-place during a migration. Cleanup is scoped to state the process owns, so an interrupted migration can't corrupt shared state.

### 5. Usage-ranked tool index including MCP tools (2026.11.10-beta.1)

An opt-in index ranks tools by prior usage frequency and surfaces them to the agent alongside search results. MCP tools are included. This complements on-demand skill loading by applying the same lazy-load principle to tools.

---

## What we can use in Lexicon

Ranked by value-to-effort ratio. Each row maps to a real file verified in the source tree.

| # | Pattern | Effort | File(s) |
|---|---|---|---|
| 1 | **On-demand skill loading** — score skill metadata against current context; load full SKILL.md only when matched | Low | `src/engine/skills.py` |
| 2 | **Credential redaction in compactor** — strip/mask secrets before they enter a compressed turn | Low–Med | `src/engine/context/compactor.py` |
| 3 | **Overflow fallback to secondary model** — when context-window overflow is caught, retry on a larger-context model before failing | Low | `src/engine/llm/router.py` |
| 4 | **Copy-and-swap session migration** — write new session state to a temp location and rename, never patch live state | Medium | `src/gateway/session.py`, `src/gateway/server.py` |
| 5 | **MCP-event triggered cron jobs** — extend scheduler to accept an MCP event as a trigger, not only a cron expression | High | `src/cron/scheduler.py`, `src/engine/tools/registry.py` |

---

## My picks for what to spike next

**Spike 1 — On-demand skill loading (`src/engine/skills.py`)**  
The skill registry already scans metadata and builds a lightweight index. The missing piece is a relevance step: score skill `triggers` and `description` against the incoming message before deciding whether to inject the full SKILL.md. This keeps the system prompt lean as the library grows and is a low-risk, self-contained change.

**Spike 2 — Credential redaction in `src/engine/context/compactor.py`**  
Compaction squashes prior turns into summaries. If an earlier turn contained a key or token, the summary may echo it. A regex/entropy scan pass before the compacted block is emitted would close this. High safety value, narrow blast radius.
