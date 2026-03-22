# Lexicon.ai - Complete System Design

## Context
A real-time meeting assistant agent system. Listens to meetings and, based on persona (software engineer first, later doctor/manufacturer), provides contextual suggestions: terminology you can use, design patterns, effective answers, and keywords. Uses a Chief Agent + Sub-Agent hierarchy with per-agent workspaces, skills, memory, and cron scheduling.

---

## Tech Stack
- **Backend**: Python 3.12+ (FastAPI + WebSockets)
- **Frontend**: React (Vite) + TailwindCSS
- **LLM**: Anthropic Python SDK (Claude, primary), provider abstraction for others
- **Knowledge Search**: QMD (on-device hybrid search: BM25 + vector + LLM rerank, all local)
- **Knowledge Storage**: Obsidian vault (markdown files) — single source of truth
- **Term Feedback**: SQLite sidecar (times_suggested, times_used_by_user tracking)
- **Audio/STT**: Deepgram (client-side browser WS, primary), Whisper API (fallback)
- **Gateway**: FastAPI WebSocket + REST endpoints
- **Cron**: APScheduler (Python scheduler with cron expressions)
- **Package Management**: uv
- **Async**: asyncio throughout
- **QMD access**: MCP server or CLI subprocess

---

## Architecture (4 Layers)

```
┌──────────────────────────────────────────────────────────────────┐
│  PRESENTATION (React + Vite + TailwindCSS)                       │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ AudioCapture │  │TranscriptView│  │ SuggestionPanel        │  │
│  │ (Web Audio   │  │ (live text)  │  │ ┌─ SuggestionCard     │  │
│  │  + Deepgram  │  │              │  │ ├─ TermSuggestionCard  │  │
│  │  WS direct)  │  │              │  │ └─ streaming text      │  │
│  └──────┬───────┘  └──────────────┘  └────────────────────────┘  │
│         │                                                        │
│  WebSocket Client (wsClient.ts)                                  │
└─────────┼────────────────────────────────────────────────────────┘
          │ WebSocket JSON frames (ws://127.0.0.1:18800/ws)
          │
┌─────────┼────────────────────────────────────────────────────────┐
│  GATEWAY │ (FastAPI)                                              │
│         ▼                                                        │
│  ┌──────────┐    ┌────────────┐    ┌──────────────┐             │
│  │ WS       │───▸│  Router    │───▸│ Session      │             │
│  │ Endpoint │    │ (by type)  │    │ Manager      │             │
│  └──────────┘    └─────┬──────┘    └──────────────┘             │
│                        │                                         │
│               ┌────────┼────────┐                                │
│               ▼        ▼        ▼                                │
│          transcript  memory   cron                               │
│          /meeting    .query   .manage                            │
│                                                                  │
│  ┌──────────────────┐   REST: /api/settings, /api/memories      │
│  │ Cron (APScheduler)│   /api/terms, /api/sessions               │
│  └──────────────────┘                                            │
└──────────┬───────────────────────────────────────────────────────┘
           │ async function calls
           │
┌──────────┼───────────────────────────────────────────────────────┐
│  ENGINE  │ (Python asyncio)                                      │
│          ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ CHIEF AGENT (orchestrator)                               │     │
│  │  ├─ Detects "suggestion moments" from transcript         │     │
│  │  ├─ Matches skill triggers (keywords + context)          │     │
│  │  ├─ Routes to sub-agents via route_to_agent tool         │     │
│  │  └─ Can route BOTH suggestion + terminology in parallel  │     │
│  └────────┬──────────────────────────┬──────────────────────┘     │
│           │                          │                            │
│   ┌───────▼────────┐    ┌───────────▼──────────┐                │
│   │ SW Engineer    │    │ Doctor (future)       │                │
│   │ Sub-Agent      │    │ Sub-Agent             │                │
│   │                │    │                       │                │
│   │ Skills:        │    │ Skills:               │                │
│   │ ├ design-patt  │    │ ├ diagnosis           │                │
│   │ ├ system-desgn │    │ ├ terminology         │                │
│   │ ├ paper-reader │    │ └ ...                 │                │
│   │ ├ code-review  │    └───────────────────────┘                │
│   │ ├ interview    │                                             │
│   │ └ terminology  │  ◀── NEW: suggests AI/tech terms            │
│   └───────┬────────┘                                             │
│           │                                                      │
│   ┌───────▼──────────────────────────────────────────────┐       │
│   │ AgentRuntime (per agent)                              │       │
│   │  input → build_system_prompt → LLM stream → tools     │       │
│   │                                                       │       │
│   │  Steering: transcript queue checked between tool calls│       │
│   │  so agent never falls behind real-time conversation   │       │
│   └───────┬──────────────────────────────────────────────┘       │
│           │                                                      │
│   ┌───────▼──────────────────────────────────────────────┐       │
│   │ Tools                                                 │       │
│   │  ├ qmd_search    — hybrid search via QMD (BM25+vec)   │       │
│   │  ├ vault_write   — write .md files to Obsidian vault   │       │
│   │  ├ vault_read    — read specific vault files            │       │
│   │  ├ term_feedback — bump used/dismissed in SQLite        │       │
│   │  ├ paper_fetch   — fetch & summarize arxiv papers       │       │
│   │  └ web_search    — web search for context               │       │
│   └──────────────────────────────────────────────────────┘       │
└──────────┬───────────────────────────────────────────────────────┘
           │
┌──────────┼───────────────────────────────────────────────────────┐
│  STORAGE │                                                        │
│          ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ KNOWLEDGE BASE (QMD + Obsidian Vault + SQLite)           │     │
│  │                                                          │     │
│  │  Obsidian Vault (~/.lexicon/vault/)                      │     │
│  │    └─ Single source of truth: all knowledge as .md files │     │
│  │    └─ terms/, patterns/, papers/, insights/, daily/      │     │
│  │    └─ YAML frontmatter + wiki-links                      │     │
│  │    └─ User can browse/edit in Obsidian app               │     │
│  │                                                          │     │
│  │  QMD (on-device search engine)                           │     │
│  │    └─ Indexes the vault automatically                    │     │
│  │    └─ BM25 full-text + vector embeddings (local GGUF)    │     │
│  │    └─ LLM rerank + query expansion (all local, no API)   │     │
│  │    └─ SQLite index: ~/.cache/qmd/index.sqlite            │     │
│  │    └─ Access via MCP server or CLI                       │     │
│  │                                                          │     │
│  │  SQLite Sidecar (~/.lexicon/feedback.sqlite)             │     │
│  │    └─ Term feedback: times_suggested, times_used_by_user │     │
│  │    └─ Session tracking                                   │     │
│  │    └─ Lightweight, no server needed                      │     │
│  │                                                          │     │
│  │  Working Memory (in-process deque)                       │     │
│  │    └─ Current turn context window                        │     │
│  │                                                          │     │
│  │  Short-Term (JSONL files, 7-day rolling)                 │     │
│  │    └─ ~/.lexicon/sessions/<agentId>/short_term.jsonl     │     │
│  │                                                          │     │
│  │  Episodic (JSONL per meeting)                            │     │
│  │    └─ ~/.lexicon/sessions/<agentId>/episodic/<id>.jsonl  │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ MEMORY PATTERNS (from research)                          │     │
│  │                                                          │     │
│  │  Hybrid Search (handled by QMD):                         │     │
│  │    BM25 + vector + RRF + LLM rerank — all local          │     │
│  │    Query expansion for better recall                     │     │
│  │    Smart chunking respects markdown headings             │     │
│  │                                                          │     │
│  │  Progressive Disclosure:                                 │     │
│  │    QMD returns chunks → agent reads full file if needed  │     │
│  │                                                          │     │
│  │  Diary + Reflect (post-meeting):                         │     │
│  │    Meeting ends → auto-diary → cron reflects → patterns  │     │
│  │    written to vault as .md files                         │     │
│  │                                                          │     │
│  │  Temporal Consolidation (cron):                          │     │
│  │    Nightly: compress day's meetings into digest .md      │     │
│  │    Weekly: merge duplicates, archive old files           │     │
│  │    Monthly: prune low-relevance vault files              │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Search & Storage

### QMD — On-Device Hybrid Search

QMD indexes the Obsidian vault and provides hybrid search with zero API costs:

```
qmd collection add ~/.lexicon/vault --name lexicon
```

QMD handles:
- **BM25 full-text search** (keyword matching)
- **Vector embeddings** (semantic similarity, local GGUF model ~300MB)
- **LLM reranking** (local GGUF model ~640MB)
- **Query expansion** (local GGUF model ~1.1GB)
- **Reciprocal Rank Fusion** (merges BM25 + vector results)
- **Smart chunking** (~900 tokens, respects markdown headings)

Access via MCP server (for Claude integration) or CLI/SDK from Python.

All models run locally. No API calls. No Postgres. No cloud dependency.

### SQLite Sidecar — Term Feedback Tracking

QMD is a search engine, not a CRUD database. For structured data that
needs counters and updates, we use a small local SQLite file:

```sql
-- ~/.lexicon/feedback.sqlite

-- Term feedback loop (tracks what the user actually uses)
CREATE TABLE term_feedback (
    term_slug       TEXT PRIMARY KEY,       -- matches vault/terms/<slug>.md
    times_suggested INTEGER DEFAULT 0,
    times_used      INTEGER DEFAULT 0,
    times_dismissed INTEGER DEFAULT 0,
    last_suggested  TEXT,                   -- ISO timestamp
    last_used       TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Session tracking
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,
    title           TEXT,
    persona         TEXT NOT NULL,
    started_at      TEXT DEFAULT (datetime('now')),
    ended_at        TEXT,
    status          TEXT DEFAULT 'active',
    metadata        TEXT DEFAULT '{}'       -- JSON string
);
```

---

## Hybrid Search Flow (QMD — all local)

```
Query: "event sourcing"
        │
        ▼
   QMD Query Expansion (local LLM)
   "event sourcing" → ["event sourcing pattern", "CQRS event store",
                        "event-driven architecture"]
        │
        ├─→ BM25 full-text (SQLite FTS)
        │   → keyword matches across all vault .md files
        │
        ├─→ Vector similarity (local embeddings, GGUF)
        │   → semantic matches across all vault .md files
        │
        ▼
   Reciprocal Rank Fusion (RRF)
   Merge + deduplicate + bonus for multi-query hits → top 30
        │
        ▼
   LLM Rerank (local GGUF reranker — no API cost)
   Position-aware blending: retrieval confidence × reranker score
   → top results with scores
        │
        ▼
   Agent receives ranked chunks with source file paths
   Can call vault_read(path) to get full file content if needed

No API calls. No cloud. ~2GB models cached locally.
```

---

## Term Intelligence Flow

```
Transcript: "We need to figure out how to make the LLM use our company docs"
        │
        ▼
Chief Agent detects topic → routes to SW Engineer with terminology skill
        │
        ▼
qmd_search tool queries the vault:
   - QMD hybrid search on vault/terms/ collection
   - Returns relevant term .md files with scores
        │
        ▼
Agent reads matched term files (vault_read):
   - Gets definition, use_in_sentence, difficulty, context_tags
   - Checks SQLite feedback: skip terms already suggested this meeting
   - Filters by difficulty (learned from usage patterns over time)
        │
        ▼
Returns TermSuggestionCard:
   ┌──────────────────────────────────────────┐
   │ Terms You Can Use                        │
   │                                          │
   │ ▸ RAG (Retrieval-Augmented Generation)   │
   │   "We should implement a RAG pipeline —  │
   │    retrieve relevant docs, then feed     │
   │    them as context to the LLM"           │
   │                                          │
   │ ▸ Grounding                              │
   │   "This grounds the model's responses    │
   │    in factual data, reducing             │
   │    hallucinations"                       │
   │                                          │
   │ Related: vector store, chunking,         │
   │ semantic search                          │
   └──────────────────────────────────────────┘

Feedback loop:
   Agent suggests "RAG" → user clicks [Used] or [Dismiss]
   → SQLite: bumps times_used or times_dismissed
   → Over time: agent learns which terms the user actually uses
   → High times_used / times_suggested ratio = boost in future rankings
```

---

## Data Flow: Meeting Start → Suggestion

```
1. User clicks [Start Meeting]
   └─→ Browser: getUserMedia() → AudioWorklet → PCM chunks → Deepgram WS
   └─→ Browser sends meeting.control(start) to Gateway WS

2. Gateway: SessionManager creates session
   └─→ Loads Chief Agent workspace + SW Engineer workspace
   └─→ Loads skills, initializes memory managers
   └─→ Returns meeting.state(active) to browser

3. Deepgram returns transcript chunks to browser
   └─→ TranscriptBuffer merges partials, flushes every 2s / 5+ words
   └─→ Browser sends transcript.chunk to Gateway

4. Gateway Router → Chief Agent
   └─→ Chief evaluates context + skill triggers
   └─→ Detects "suggestion moment"
   └─→ Calls route_to_agent(software-engineer, context, skills=[...])

5. SW Engineer Sub-Agent runs:
   a. Builds system prompt (IDENTITY + SOUL + AGENT + matched SKILLs)
   b. Knowledge retrieval:
      - Working memory (deque): current meeting context
      - QMD hybrid search: vault/terms/, vault/patterns/, vault/papers/
      - Short-term (JSONL): recent meetings
      - Episodic: past meeting decisions
   c. Term retrieval (if terminology skill matched):
      - QMD search on vault/terms/ → read matched files
      - SQLite feedback check (skip recently suggested)
   d. Sends to Claude API (streaming)

6. Response streams back:
   Sub-Agent → Chief → Gateway → WebSocket → Browser
   └─→ suggestion.stream events with text deltas
   └─→ UI renders SuggestionCard / TermSuggestionCard

7. Post-response:
   └─→ Episodic: append chunk + suggestion to meeting JSONL
   └─→ Working memory: update deque (evict oldest if full)
   └─→ Refresh-on-retrieval: bump access_count on used memories
   └─→ Steering: check queue for new transcript chunks
```

---

## Knowledge Base Architecture

### Single Source of Truth: Obsidian Vault + QMD

The knowledge base is the Obsidian vault. Period.
- **Obsidian vault** (`~/.lexicon/vault/`) — all knowledge as .md files, browsable, manually editable, wiki-linked
- **QMD** indexes the vault automatically — BM25 + vector + LLM rerank, all local
- **SQLite sidecar** (`~/.lexicon/feedback.sqlite`) — only for term feedback counters and session tracking

No Postgres. No cloud database. No sync jobs. Write a .md file → QMD indexes it → agent can search it.

### Obsidian Vault Structure

```
~/.lexicon/vault/
├── terms/                          # One file per term/concept
│   ├── agentic-orchestration.md
│   ├── chain-of-thought.md
│   ├── retrieval-augmented-generation.md
│   └── ...
├── patterns/                       # Design patterns, architectures
│   ├── event-sourcing.md
│   ├── rag-pipeline.md
│   ├── react-agent-pattern.md
│   └── ...
├── papers/                         # Paper summaries (from arxiv, blogs)
│   ├── 2026-03-attention-is-all-you-need-v2.md
│   └── ...
├── insights/                       # Blog summaries, analysis, pro/cons
│   ├── fine-tuning-vs-rag-tradeoffs.md
│   └── ...
└── daily/                          # Daily digest logs (what was scanned)
    ├── 2026-03-17.md
    └── ...
```

### Obsidian File Format (per term/concept)

```markdown
---
term: agentic orchestration
category: agents
difficulty: intermediate
related: [multi-agent, delegation, handoff, tool-use]
context_tags: [meeting, architecture, design-discussion]
source: paper:arxiv/2026.12345
created: 2026-03-17
---

# Agentic Orchestration

**Definition:** A pattern where a central agent coordinates multiple
specialized sub-agents, deciding which agent handles which part of a
task based on context.

## Use in Sentence
"Instead of one monolithic prompt, we could use agentic orchestration —
have a planner agent break this down and delegate to specialized agents
for each subtask."

## Key Points
- Central orchestrator decides routing (not hardcoded)
- Each sub-agent has own context/tools
- Examples: CrewAI, AutoGen, OpenClaw's Chief Agent pattern

## Gotchas
- Overhead: each delegation = another LLM call = latency + cost
- Context loss between agents if not managed

## Related
- [[multi-agent]] — the broader concept
- [[delegation]] — how tasks get handed off
```

The `[[double-bracket]]` links are Obsidian wiki-links — they create a visual knowledge graph.

### Knowledge Categories (8 top-level, split later as KB grows)

| Category | What Goes In | Example Terms |
|----------|-------------|---------------|
| `llm-foundations` | Models, training, inference | transformer, attention, tokenization, RLHF, DPO, quantization |
| `agents` | Agentic patterns, orchestration, tool use | ReAct, function calling, multi-agent, swarm, delegation, handoff |
| `rag-and-retrieval` | RAG, search, embeddings, chunking | vector search, BM25, hybrid search, reranking, GraphRAG |
| `evals-and-quality` | Evaluation, testing, guardrails | LLM-as-judge, red-teaming, hallucination, faithfulness |
| `infra-and-serving` | Deployment, scaling, cost, latency | vLLM, KV cache, speculative decoding, model routing |
| `context-engineering` | Prompts, context management, memory | system prompt, few-shot, prompt caching, memory patterns |
| `products-and-platforms` | Specific tools (Claude, Codex, etc.) | Claude Code, Codex, Cursor, LangChain, CrewAI, Harness |
| `design-patterns` | Software architecture for AI systems | event sourcing, CQRS, saga, circuit breaker, streaming |

---

## Skills Architecture (Two Layers)

Skills are organized into two layers: knowledge building (fills the KB) and real-time (reads from KB during meetings).

### Layer 1: Knowledge Building Skills (cron + post-meeting)

These run BEFORE and BETWEEN meetings. They populate the Obsidian vault (QMD auto-indexes):

| Skill | When It Runs | What It Produces |
|-------|-------------|-----------------|
| `paper-reader` | Cron (daily 7am) | Reads arxiv papers → extracts terms, patterns, findings → vault/papers/ + vault/terms/ |
| `web-researcher` | Cron (daily 7am) | Scans AI blogs/RSS → extracts insights, terms → vault/insights/ + vault/terms/ |
| `meeting-digest` | After every meeting | Processes transcript → extracts decisions, new terms, topics → vault/ + episodic JSONL |
| `knowledge-consolidator` | Cron (weekly) | Merges duplicates, archives stale files, deduplicates vault terms |

### Layer 2: Real-Time Suggestion Skills (during meetings)

These run DURING meetings. They read FROM the knowledge base:

| Skill | Trigger | Output Type | Reads From |
|-------|---------|-------------|-----------|
| `term-explainer` | Unknown term detected | Explain what it means | QMD → vault/terms/ |
| `term-suggest` | Opportunity to use impressive vocab | Term + ready-to-use sentence | QMD → vault/terms/ (filtered by context) |
| `pro-con-analyzer` | Someone proposes a solution | Pros, cons, what to say | QMD → vault/patterns/ + vault/insights/ |
| `design-pattern-suggest` | Architecture discussion | Relevant pattern/approach | QMD → vault/patterns/ + vault/papers/ |
| `smart-question` | Pause / Q&A moment | Sharp question to ask | QMD → full vault + current transcript |
| `meeting-prep` | Pre-meeting (user sends agenda) | Brief with terms, patterns, talking points | QMD → vault/ (filtered by topics) |

### Knowledge Flow

```
INPUT SOURCES                    KNOWLEDGE BASE               REAL-TIME OUTPUT
                                                              (during meetings)
Arxiv papers ──┐                ┌──────────────┐
  (daily cron)  │               │              │    ┌─ term-explainer
                ├──▸ Layer 1 ──▸│  Obsidian    │    ├─ term-suggest
AI blogs/RSS ──┤    Skills      │  Vault       │    ├─ pro-con-analyzer
  (daily cron)  │  (write .md)  │  (.md files) │──▸ ├─ design-pattern-suggest
                │               │      │       │    ├─ smart-question
Past meetings ─┤               │      ▼       │    └─ meeting-prep
  (post-mtg)    │               │  QMD indexes │
                │               │  (auto, local│
You manually ──┤               │   BM25+vec)  │
  (edit vault)  │               │              │
                │               └──────────────┘
YouTube ────────┘
  (future)
```

### Knowledge Input Sources

| Source | Method | When | Status |
|--------|--------|------|--------|
| Arxiv papers | `paper-reader` skill via cron | Daily 7am | Phase 2C |
| AI blogs/RSS | `web-researcher` skill via cron | Daily 7am | Phase 2C |
| User manual input | Edit .md files in Obsidian vault | Anytime | Phase 2C |
| Past meeting transcripts | `meeting-digest` skill (post-meeting) | After each meeting | Phase 2C |
| YouTube videos | Future tool: transcript → extract → KB | Later | Backlog |
| PDFs user reads | Future: drag & drop → parse → KB | Later | Backlog |
| Twitter/X threads | Future: save link → extract → KB | Later | Backlog |

### Skill Best Practices (OpenClaw guidelines)

Skills follow OpenClaw's SKILL.md pattern:
- **A skill is a FOLDER**, not just a file — can include references/, scripts/, assets/
- **Progressive disclosure**: SKILL.md tells agent what's available, it reads deeper files on demand
- **Description field is for triggering**, not summarizing — say when to trigger, not the workflow
- **Gotchas section**: highest-signal content — built from actual agent failures
- **Don't state the obvious**: focus on knowledge Claude wouldn't have by default
- **Don't railroad**: be specific about WHAT, flexible about HOW
- **Keep SKILL.md under 500 lines**, reference files over 100 lines get a TOC
- **Store scripts & code**: give Claude composable tools, not boilerplate to reconstruct
- **Iterate via autoresearch**: write → test → measure → improve (3-6 yes/no scoring criteria)

---

## Post-Meeting & Cron Flows

```
Meeting ends → User clicks [Stop]
   └─→ meeting-digest skill runs:
       ├─→ Summarize meeting → vault/daily/
       ├─→ Extract new terms heard → vault/terms/ (QMD auto-indexes)
       ├─→ Extract decisions/patterns → vault/insights/
       └─→ Append to episodic memory (JSONL)

Daily (7am) — Knowledge Scan:
   └─→ paper-reader skill:
       ├─→ Check arxiv for papers matching filters (keywords + categories)
       ├─→ Read abstract + intro + conclusion
       ├─→ Extract terms, patterns, findings
       ├─→ Write to vault/papers/ + vault/terms/
       └─→ QMD auto-indexes new files
   └─→ web-researcher skill:
       ├─→ Check RSS feeds / blog list (Anthropic, OpenAI, Simon Willison, etc.)
       ├─→ Extract insights, new terms
       ├─→ Write to vault/insights/ + vault/terms/
       └─→ QMD auto-indexes new files
   └─→ Write daily digest → vault/daily/YYYY-MM-DD.md

Nightly (11pm) — Temporal Consolidation:
   └─→ Read today's episodic entries
   └─→ Extract patterns → write as vault .md files

Weekly (Sunday) — Reflect + Consolidate:
   └─→ knowledge-consolidator skill:
       ├─→ Scan short-term JSONL for recurring themes
       ├─→ Deduplicate vault terms (merge similar .md files)
       ├─→ Archive stale vault files (move to vault/archive/)
       ├─→ Promote frequently-accessed short-term patterns → vault/patterns/
       └─→ Update term difficulty in frontmatter based on usage

Monthly — Cleanup:
   └─→ Archive old episodic JSONL (compress)
   └─→ Update term difficulty ratings based on usage patterns
   └─→ Generate monthly knowledge growth report
```

---

## Project Structure

```
lexicon.ai/
├── pyproject.toml
├── .env.example
├── PLAN.md
├── TODO.md
│
├── src/
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── types.py               # Pydantic models
│   │   ├── config.py              # Config from ~/.lexicon/config.json
│   │   ├── frontmatter.py         # YAML frontmatter parser
│   │   ├── logger.py              # Structured logging
│   │   └── constants.py           # Ports, paths, defaults
│   │
│   ├── search/                      # QMD integration (on-device hybrid search)
│   │   ├── __init__.py
│   │   ├── qmd_client.py          # QMD CLI/MCP wrapper (query, search, get)
│   │   └── collections.py         # Manage QMD collections (add vault, reindex)
│   │
│   ├── feedback/                    # SQLite sidecar for structured data
│   │   ├── __init__.py
│   │   ├── db.py                  # SQLite connection + schema setup
│   │   ├── terms.py               # Term feedback CRUD (suggested, used, dismissed)
│   │   └── sessions.py            # Session tracking CRUD
│   │
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── server.py              # FastAPI app + WS + REST
│   │   ├── router.py              # Message routing by type
│   │   ├── session.py             # Session lifecycle
│   │   ├── protocol.py            # Message types (Pydantic)
│   │   └── cron_scheduler.py      # APScheduler integration
│   │
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── runtime.py             # AgentRuntime execution loop
│   │   ├── registry.py            # Agent registry
│   │   ├── workspace.py           # Load AGENT.md, SOUL.md, IDENTITY.md
│   │   ├── skills.py              # 3-tier skill loading + trigger matching
│   │   ├── orchestrator.py        # Chief + sub-agent routing
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py        # Abstract LLM provider (ABC)
│   │   │   ├── claude_provider.py # Anthropic SDK streaming
│   │   │   └── openai_provider.py # OpenAI fallback
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── manager.py         # Unified search/store/recall
│   │   │   ├── working.py         # In-process deque
│   │   │   ├── short_term.py      # JSONL, 7-day rolling
│   │   │   └── episodic.py        # Per-meeting JSONL
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── registry.py        # Tool registry
│   │       ├── qmd_search.py      # Search vault via QMD (hybrid)
│   │       ├── vault_write.py     # Write .md files to vault
│   │       ├── vault_read.py      # Read vault files
│   │       ├── term_feedback.py   # Bump used/dismissed in SQLite
│   │       ├── paper_fetch.py     # Fetch & summarize papers
│   │       └── web_search.py      # Web search
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── transcription.py       # STT provider ABC
│   │   ├── deepgram_provider.py   # Deepgram streaming
│   │   ├── whisper_provider.py    # Whisper fallback
│   │   └── buffer.py              # Transcript chunking/buffering
│   │
│   ├── vault/                        # Obsidian vault read/write utilities
│   │   ├── __init__.py
│   │   ├── writer.py              # Write .md files to vault (terms, papers, insights)
│   │   └── reader.py              # Read/parse vault .md files (frontmatter + body)
│   │
│   └── seeds/                      # Seed data
│       ├── __init__.py
│       ├── terms_seed.py          # ~200-300 AI/SWE terms data
│       └── load_seeds.py          # Write seed terms as .md files to vault/terms/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Meeting.tsx
│   │   │   ├── Knowledge.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── meeting/
│   │   │   │   ├── MeetingPanel.tsx
│   │   │   │   ├── AudioCapture.tsx
│   │   │   │   ├── TranscriptView.tsx
│   │   │   │   ├── SuggestionPanel.tsx
│   │   │   │   ├── SuggestionCard.tsx
│   │   │   │   ├── TermSuggestionCard.tsx    # NEW
│   │   │   │   └── MeetingControls.tsx
│   │   │   ├── persona/
│   │   │   │   ├── PersonaSelector.tsx
│   │   │   │   └── PersonaConfig.tsx
│   │   │   ├── knowledge/
│   │   │   │   ├── KnowledgeBrowser.tsx
│   │   │   │   ├── SearchBar.tsx
│   │   │   │   └── MemoryCard.tsx
│   │   │   └── shared/
│   │   │       ├── WebSocketProvider.tsx
│   │   │       └── StreamingText.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useAudioCapture.ts
│   │   │   ├── useMeeting.ts
│   │   │   └── usePersona.ts
│   │   └── lib/
│   │       ├── wsClient.ts
│   │       └── audio.ts
│   └── public/
│       └── audio-processor.js
│
├── workspaces/
│   ├── chief/
│   │   ├── AGENT.md
│   │   ├── SOUL.md
│   │   ├── IDENTITY.md
│   │   └── skills/
│   │       ├── meeting-orchestration/SKILL.md
│   │       └── context-routing/SKILL.md
│   ├── software-engineer/
│   │   ├── AGENT.md
│   │   ├── SOUL.md
│   │   ├── IDENTITY.md
│   │   └── skills/
│   │       │   # Layer 1: Knowledge Building
│   │       ├── paper-reader/
│   │       │   ├── SKILL.md
│   │       │   └── references/
│   │       │       ├── arxiv-filters.md      # Keywords, categories to scan
│   │       │       └── extraction-template.md # How to extract terms/patterns
│   │       ├── web-researcher/
│   │       │   ├── SKILL.md
│   │       │   └── references/
│   │       │       └── blog-sources.md       # RSS feeds, blogs to follow
│   │       ├── meeting-digest/
│   │       │   └── SKILL.md
│   │       ├── knowledge-consolidator/
│   │       │   └── SKILL.md
│   │       │   # Layer 2: Real-Time Suggestions
│   │       ├── term-explainer/
│   │       │   ├── SKILL.md
│   │       │   └── references/
│   │       │       └── common-ai-terms.md    # Seed list of terms
│   │       ├── term-suggest/
│   │       │   ├── SKILL.md
│   │       │   └── references/
│   │       │       └── impressive-vocab.md   # Terms + sentences by category
│   │       ├── pro-con-analyzer/
│   │       │   └── SKILL.md
│   │       ├── design-pattern-suggest/
│   │       │   ├── SKILL.md
│   │       │   └── references/
│   │       │       └── patterns.md           # Key patterns with when-to-use
│   │       ├── smart-question/
│   │       │   ├── SKILL.md
│   │       │   └── references/
│   │       │       └── question-bank.md      # Domain-specific smart questions
│   │       └── meeting-prep/
│   │           └── SKILL.md
│   └── doctor/
│       ├── AGENT.md
│       ├── SOUL.md
│       └── IDENTITY.md
│
├── tests/
│   ├── test_search/
│   ├── test_feedback/
│   ├── test_gateway/
│   ├── test_engine/
│   ├── test_memory/
│   └── test_audio/
│
└── scripts/
    ├── setup.sh                    # Install deps, init dirs, install QMD, create collection
    ├── dev.sh
    └── seed_terms.py               # One-time: seed terms as .md files into vault/terms/
```

**Runtime data** (local machine):
```
~/.lexicon/
├── config.json                     # API keys, STT provider, preferences
├── feedback.sqlite                 # Term feedback + session tracking
├── workspaces/                     # Active workspaces (copied from templates)
├── skills/                         # User-managed shared skills
├── vault/                          # Obsidian vault (knowledge base)
│   ├── terms/                      # One .md per term/concept
│   ├── patterns/                   # Design patterns, architectures
│   ├── papers/                     # Paper summaries
│   ├── insights/                   # Blog summaries, analysis
│   └── daily/                      # Daily digest logs
├── sessions/
│   └── <agentId>/
│       ├── short_term.jsonl
│       └── episodic/<meetingId>.jsonl
├── cron/
│   ├── jobs.json
│   └── runs/
└── logs/
    └── gateway.log
```

---

## Python Dependencies

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "websockets>=14.0",
    "anthropic>=0.42",
    "apscheduler>=3.10",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "python-frontmatter>=1.1",
    "watchfiles>=1.0",
    "httpx>=0.28",
    "deepgram-sdk>=3.8",
    "aiosqlite>=0.20",             # Async SQLite for feedback sidecar
]
```

### External: QMD (installed separately)
```sh
npm install -g @tobilu/qmd         # or: bun install -g @tobilu/qmd
qmd collection add ~/.lexicon/vault --name lexicon
```
QMD runs as a separate process (MCP server or CLI). Python calls it via subprocess or HTTP.
Models auto-download on first use (~2GB total, cached at ~/.cache/qmd/models/).
