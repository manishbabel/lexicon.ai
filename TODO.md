# Lexicon.ai - Implementation TODO

## Phase 1: Foundation ✅ DONE
> All files built and imports verified.
> Note: src/db/ files (pool.py, migrations.py, embeddings.py, memories.py, terms.py, sessions_db.py)
> are now obsolete — replaced by QMD + SQLite. Will be removed in cleanup.

- [x] 1.1 `pyproject.toml` + `uv sync` (36 packages installed)
- [x] 1.2 `.env.example`
- [x] 1.3 `src/shared/constants.py`
- [x] 1.4 `src/shared/types.py`
- [x] 1.5 `src/shared/config.py`
- [x] 1.6 `src/shared/frontmatter.py`
- [x] 1.7 `src/shared/logger.py`
- [x] ~~1.8 `src/db/pool.py`~~ — OBSOLETE (replaced by QMD)
- [x] ~~1.9 `src/db/migrations.py`~~ — OBSOLETE (replaced by QMD + SQLite sidecar)
- [x] ~~1.10 `src/db/embeddings.py`~~ — OBSOLETE (QMD generates embeddings locally)
- [x] 1.11 `src/engine/llm/provider.py`
- [x] 1.12 `src/engine/llm/claude_provider.py`
- [x] 1.13 `src/engine/workspace.py`
- [x] 1.14 `src/engine/runtime.py` (basic — enhanced in Phase 2A)
- [x] 1.15 `src/engine/registry.py`
- [x] 1.16 `workspaces/chief/` templates
- [x] 1.17 `workspaces/software-engineer/` templates
- [x] 1.18 `workspaces/doctor/` placeholders
- [x] 1.19 `scripts/setup.sh`
- [x] 1.20 `scripts/smoke_test.py`

---

## Phase 2A: Command Queue (OpenClaw pattern) ✅ DONE
> Lane-based FIFO queue, runner, and enhanced runtime with steering + lazy skills.

- [x] 2.1 `src/engine/queue.py` — Lane-based FIFO command queue
- [x] 2.2 `src/engine/runner.py` — Agent run executor
- [x] 2.3 Enhanced `src/engine/runtime.py` — OpenClaw patterns

---

## Phase 2B: Gateway ✅ DONE
> WebSocket gateway with protocol, sessions, routing, and server.

- [x] 2.4 `src/gateway/protocol.py` — WS message types + SuggestionCategory enum
- [x] 2.5 `src/gateway/session.py` — Session lifecycle
- [x] 2.6 `src/gateway/router.py` — Message routing + dispatch
- [x] 2.7 `src/gateway/server.py` — FastAPI app + WS endpoint + REST

---

## Phase 2C: Skills + Vault + QMD ✅ DONE
> Skill loader, skill folders, Obsidian vault utilities, QMD integration, SQLite sidecar.

### Skills Loader
- [x] 2.8 `src/engine/skills.py` — Skill registry + lazy loader

### Skill Folder Structure
- [x] 2.9 `software-engineer/skills/paper-reader/SKILL.md`
- [x] 2.10 `software-engineer/skills/web-researcher/SKILL.md`
- [x] 2.11 `software-engineer/skills/meeting-digest/SKILL.md`
- [x] 2.12 `software-engineer/skills/knowledge-consolidator/SKILL.md`
- [x] 2.13 `software-engineer/skills/term-explainer/SKILL.md`
- [x] 2.14 `software-engineer/skills/term-suggest/SKILL.md`
- [x] 2.15 `software-engineer/skills/pro-con-analyzer/SKILL.md`
- [x] 2.16 `software-engineer/skills/design-pattern-suggest/SKILL.md`
- [x] 2.17 `software-engineer/skills/smart-question/SKILL.md`
- [x] 2.18 `software-engineer/skills/meeting-prep/SKILL.md`
- [x] 2.19 `chief/skills/meeting-orchestration/SKILL.md`
- [x] 2.20 `chief/skills/context-routing/SKILL.md`

### QMD Integration
- [x] 2.21 `src/search/qmd_client.py` — QMD wrapper
- [x] 2.22 `src/search/collections.py` — Manage QMD collections

### SQLite Sidecar
- [x] 2.23 `src/feedback/db.py` — SQLite connection + schema
- [x] 2.24 `src/feedback/terms.py` — Term feedback CRUD
- [x] 2.25 `src/feedback/sessions.py` — Session tracking CRUD

### Obsidian Vault Utilities
- [x] 2.26 `src/vault/writer.py` — Write .md files to vault
- [x] 2.27 `src/vault/reader.py` — Read/parse vault .md files

### Cleanup + Scripts
- [x] 2.28–2.31 Cleanup + dev scripts

---

## Phase 3: Memory + Tools + Seeding ✅ DONE
> Memory system wired into agents. Agent tools for search/write. Initial KB seeding.

- [x] 3.1–3.4 Memory system (working, short-term, episodic, manager)
- [x] 3.5–3.10 Agent tools (registry, qmd_search, vault_write, vault_read, paper_fetch, term_feedback, setup)
- [x] 3.11–3.13 Seeding (50 AI/SWE terms)

---

## Phase 4: Audio + Frontend ✅ DONE
> Working React UI with live audio capture, transcript streaming, suggestion cards.

- [x] 4.1 `src/audio/transcription.py` — STT provider ABC
- [x] 4.2 `src/audio/deepgram_provider.py` — Deepgram streaming
- [x] 4.3 `src/audio/buffer.py` — transcript chunking
- [x] 4.4 Frontend scaffold: Vite 8 + React 19 + Tailwind v4
- [x] 4.5 `frontend/src/lib/wsClient.ts` — WS client with auto-reconnect
- [x] 4.6 `frontend/src/lib/audio.ts` — browser mic → Deepgram WS → transcript
- [x] 4.7 `frontend/public/audio-processor.js` — AudioWorklet PCM 16kHz
- [x] 4.8 `frontend/src/hooks/useWebSocket.ts`
- [x] 4.9 `frontend/src/hooks/useAudioCapture.ts`
- [x] 4.10 `frontend/src/hooks/useMeeting.ts` — orchestrator hook
- [x] 4.11 `frontend/src/hooks/usePersona.ts`
- [x] 4.12 `frontend/src/components/WebSocketProvider.tsx`
- [x] 4.13 `frontend/src/components/StreamingText.tsx` — renders **bold** markdown
- [x] 4.14 `frontend/src/components/SuggestionCard.tsx` — colored cards per category
- [x] 4.15 `frontend/src/components/SuggestionPanel.tsx` — grid layout
- [x] 4.16 `frontend/src/components/Teleprompter.tsx` — full-width, bold terms
- [x] 4.17 `frontend/src/components/Header.tsx` — start/pause/stop controls
- [x] 4.18 `frontend/src/components/StatusBar.tsx` — mic status, persona, suggestion count
- [x] 4.19 `frontend/src/components/MeetingPrep.tsx` — pre-meeting form
- [x] 4.20 `frontend/src/pages/Meeting.tsx` — main meeting page
- [x] 4.21 `frontend/src/pages/Settings.tsx` — API keys, model routing
- [x] 4.22 `frontend/src/App.tsx` — routing + WebSocketProvider

---

## Phase 5: Orchestration + Cron + Knowledge Pipeline ✅ DONE
> Chief→sub-agent routing. Cron jobs for knowledge building.

- [x] 5.1–5.4 Orchestration + tools (orchestrator, paper_fetch, web_search, rss_fetch)
- [x] 5.5 `src/engine/llm/openai_provider.py` — OpenAI provider
- [x] 5.6–5.11 Cron scheduler + default jobs + hooks

---

## Phase 6: OpenClaw Core Patterns ✅ DONE
> Context engine, hybrid RAG, hooks, cron, subagent spawning, model fallback.

- [x] 6.1–6.3 Context engine (token counter, compactor, pruner)
- [x] 6.4–6.5 Hybrid RAG memory (transcript index, unified search with MMR + temporal decay)
- [x] 6.6–6.8 Hook system (registry, loader, 9 built-in hooks)
- [x] 6.9–6.11 Cron scheduler (APScheduler, JSON store, 5 default jobs)
- [x] 6.12–6.13 Subagent spawning (orchestrator, route_to_agent tool)
- [x] 6.14 LiteLLM unified provider

---

## Phase 7: Tool Wiring + CLI Integrations ← CURRENT
> Goal: Wire real tool implementations into agent runtime. Integrate external CLIs.

### CLI Tool Integrations (from OpenClaw patterns)
- [x] 7.1 `src/engine/tools/obsidian_cli.py` — obsidian-cli wrapper (read, create, move, list)
  - QMD handles search (semantic), obsidian-cli handles file CRUD with wiki-link awareness
- [x] 7.2 `src/engine/tools/summarize_cli.py` — summarize CLI wrapper (URL/YouTube/PDF)
- [x] 7.3 `src/engine/tools/blogwatcher_cli.py` — blogwatcher CLI wrapper (scan, add, list, articles, mark_read)

### Agent Tool Implementations
- [x] 7.4 `web_search.py` — Upgraded to Tavily primary + DuckDuckGo fallback
- [x] 7.5 All existing tools verified: qmd_search, vault_read, vault_write, paper_fetch, term_feedback, rss_fetch

### Tool Registration + Wiring
- [x] 7.6 `setup.py` — All 17 tools registered (paper_fetch, vault_write, vault_read, qmd_search, term_feedback, web_search, rss_fetch, obsidian_read/create/move/list, summarize_url, blog_scan/add/list/articles/mark_read)
- [x] 7.7 `server.py` — `setup_tools()` called at startup, `ToolRegistry` passed to `AgentRegistry`
- [x] 7.8 `registry.py` — `AgentRegistry.create()` now calls `tool_registry.wire_into_runtime()` for every agent
- [x] 7.9 Per-agent tool allowlists — Chief: route_to_agent only, sub-agents: all except route_to_agent
- [ ] 7.10 End-to-end test: transcript → agent → tool call → result → suggestion card

---

## Phase 8: Testing
> Goal: Unit + integration tests for all critical paths.

- [ ] 8.1 `tests/test_engine/test_queue.py`
- [ ] 8.2 `tests/test_engine/test_runner.py`
- [ ] 8.3 `tests/test_engine/test_runtime.py`
- [ ] 8.4 `tests/test_engine/test_skills.py`
- [ ] 8.5 `tests/test_gateway/test_protocol.py`
- [ ] 8.6 `tests/test_gateway/test_router.py`
- [ ] 8.7 `tests/test_search/test_qmd_client.py`
- [ ] 8.8 `tests/test_feedback/test_terms.py`
- [ ] 8.9 `tests/test_memory/test_working.py`
- [ ] 8.10 `tests/test_memory/test_manager.py`
- [ ] 8.11 `tests/test_vault/test_writer.py`
- [ ] 8.12 `tests/test_audio/test_buffer.py`
- [ ] 8.13 Integration: WS → queue → agent → tool call → suggestion e2e
- [ ] 8.14 Integration: cron → paper-reader → vault → QMD indexed e2e

---

## Phase 9: UI Polish + Missing Pages ← CURRENT
> Goal: Complete the frontend — card auto-dismiss, meeting digest view, vault browser.

- [x] 9.1 Card auto-dismiss after 60s — SuggestionPanel tracks dismissed IDs, auto-removes non-streaming cards after 60s
- [x] 9.2 Max visible cards (6) — shows newest 6, header shows "3 / 12" when capped, AnimatePresence exit animations
- [x] 9.3 Meeting digest view — MeetingDigest.tsx: stats, category-grouped suggestions, "New Meeting" button
- [ ] 9.4 Knowledge.tsx — vault browser (search terms, view notes)
- [x] 9.5 Persona selector — pill-shaped dropdown in Header, disabled during active meeting
- [x] 9.6 Dark/light theme — useTheme hook + .light CSS overrides, Sun/Moon toggle in Header, localStorage persistence
- [x] 9.7 Audio level indicator — AnalyserNode RMS at 15fps, 5-bar visualizer in StatusBar

---

## Backlog (Future)
- [ ] **Slack integration** — Post meeting digests to Slack channel (OpenClaw slack skill pattern)
- [ ] **GitHub issues** — Convert action items → GitHub issues (OpenClaw gh-issues skill)
- [ ] **Apple Reminders** — Action items → native reminders (OpenClaw apple-reminders skill)
- [ ] **Peekaboo screen reader** — Read shared screen content during meetings (OpenClaw peekaboo skill)
- [ ] **Voice call agent** — Lexicon joins meeting as voice participant (OpenClaw voice-call skill)
- [ ] YouTube video listener → transcript → extract → vault
- [ ] PDF reader → drag & drop → parse → vault
- [ ] Twitter/X thread extractor → save link → extract → vault
- [ ] Autoresearch — auto-improve skills (Karpathy's method)
- [ ] Multi-persona meetings
- [ ] Skill marketplace (ClawHub pattern)
- [ ] Mobile companion — quick-add terms/notes
