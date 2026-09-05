# OpenClaw Watch — 2026-09-05

Baseline: stable 2026.5.27 · beta 2026.5.28-beta.2
Latest:   stable **2026.9.1** (Sep 3 2026) · beta **2026.9.1-beta.1**

---

## What shipped

| Version | Date | Headline |
|---------|------|---------|
| 2026.6.34 | Jun 2026 | Stability & dependency updates (no architectural notes) |
| 2026.7.1-1 | Jul 2026 | Bug-fix release (no architectural notes) |
| 2026.7.1-2 | Jul 2026 | Bug-fix release (no architectural notes) |
| **2026.8.1** | Aug 31 2026 | Conversation search; background sessions; live progress tracking; **structured agent questions**; interactive dashboards; private credential requests; **recurring work approvals** |
| **2026.8.2** | Sep 1 2026 | Home agent in dock; Linux desktop companion; **background sessions GA**; safer upgrades with rollback; voice quality; Chrome relay wake-up; four new UI themes |
| **2026.9.1** | Sep 3 2026 | Mermaid render in all apps; **personal skill libraries on shared Gateways**; quick-start setup; improved update reliability; Gateway stability; **durable Codex approvals** |
| 2026.9.1-beta.1 | Sep 2026 | Pre-release — matches 2026.9.1 feature set |

Releases 2026.6.x–2026.7.x contained only dependency bumps and hotfixes; no architectural patterns are assessed there.

---

## What's notable

### 1. Structured agent questions (2026.8.1)
Rather than emitting free-form clarification text, agents now surface typed question objects — with a `kind` (single-choice, multi-choice, text, confirm), an `options` list, and validation metadata — which the Gateway renders into UI controls. The protocol decouples *what the agent needs to know* from *how the user answers it*, enabling richer and machine-processable interactions without changing the agent loop.

### 2. Recurring work approvals (2026.8.1)
Scheduled tasks now carry an approval state persisted across restarts. Before executing a cron job, the scheduler checks a durable approval record; unapproved or expired approvals cause the job to queue a human-in-the-loop confirmation request rather than run silently. This closes the "ghost cron" failure mode where jobs run unnoticed after their original intent is forgotten.

### 3. Background sessions GA (2026.8.2)
Sessions can now detach from the active UI channel and keep running. The Gateway holds a lightweight session handle while the runtime continues executing; when a result is ready, the Gateway wakes the relevant channel (browser, relay, or notification). The separation of *session lifecycle* from *channel lifecycle* is the key architectural move.

### 4. Personal skill libraries on shared Gateways (2026.9.1)
Each user/workspace identity on a shared Gateway can maintain its own skill namespace that takes precedence over the global skill registry. The Gateway resolves skills by first checking the session-scoped namespace, then falling back to global. This enables per-workspace tool customisation without forking the runtime.

### 5. Durable Codex approvals (2026.9.1)
Approval tokens for privileged operations (Codex-level code changes, credential access) are now persisted and survive Gateway restarts. Previously an approval granted in one session could be lost on restart, forcing re-approval. The durable store makes approval state a first-class entity with an expiry TTL.

---

## What we can use in Lexicon

Ranked by value / effort (H/M/L).

### 1. Per-workspace skill namespacing in Gateway · Value H · Effort M
**What**: Wire session workspace identity into the skill resolution path so Gateway dispatches to workspace-scoped skills before the global registry.
**Where in Lexicon**:
- `src/engine/skills.py` — add `resolve(skill_name, workspace_id=None)` that checks workspace skill dirs first
- `src/gateway/session.py` — carry `workspace_id` on session objects
- `src/gateway/router.py` — pass `session.workspace_id` through to skill resolution
- `workspaces/*/skills/` — skill directories already exist per workspace; this unlocks their runtime use

**Spike**: In `src/engine/skills.py`, before the global skill lookup, check `workspaces/{session.workspace_id}/skills/{skill_name}/SKILL.md`. The workspace dirs already exist (`workspaces/chief/skills/`, `workspaces/software-engineer/skills/`, etc.); the gap is Gateway not passing workspace context to the skill resolver.

---

### 2. Structured agent questions in protocol · Value H · Effort M
**What**: Extend the gateway protocol with a typed question message kind so agents can request structured input instead of emitting raw clarification text.
**Where in Lexicon**:
- `src/gateway/protocol.py` — add `AgentQuestion` message type with `kind`, `prompt`, `options`, `required`
- `src/engine/runner.py` — detect when a tool call / response signals a clarification need and emit `AgentQuestion` instead of plain text
- `src/gateway/session.py` — handle `AgentQuestion` → send to channel; receive answer → resume runner

**Spike**: Define `AgentQuestion` dataclass in `src/gateway/protocol.py` and add a `yield_question()` helper in `src/engine/runner.py` that pauses execution until the session delivers an answer.

---

### 3. Recurring work approvals in cron · Value M · Effort L
**What**: Add an approval-state check to the scheduler so cron jobs can be gated on a durable human approval before execution.
**Where in Lexicon**:
- `src/cron/store.py` — add `ApprovalRecord(job_id, approved_at, expires_at, approved_by)` table
- `src/cron/scheduler.py` — before dispatching a job, check `store.get_approval(job_id)`; if absent or expired, emit a pending-approval notification instead of running

**Spike**: 20-line change to `src/cron/scheduler.py` + a new column in `src/cron/store.py`. Pairs well with the existing `src/cron/defaults.py` job registry.

---

### 4. Background session lifecycle separation · Value M · Effort H
**What**: Decouple session lifecycle from channel lifecycle so `src/engine/runtime.py` keeps running when the client disconnects, and results are delivered when the channel reconnects or a push notification fires.
**Where in Lexicon**:
- `src/gateway/session.py` — split `Session` into `ChannelHandle` (connection-scoped) + `SessionRecord` (runtime-scoped)
- `src/engine/runtime.py` — make the run loop channel-agnostic; write results to a queue the Gateway drains on reconnect
- `src/engine/queue.py` — already exists; extend for cross-channel durable result delivery

**Spike**: Higher effort because it touches the session/runtime boundary. Best tackled after #1 and #3 are in.

---

### 5. Durable approval tokens · Value M · Effort L
**What**: Persist approval tokens in `src/cron/store.py` with TTL so they survive Gateway restarts, eliminating silent re-approvals.
**Where in Lexicon**:
- `src/cron/store.py` — same `ApprovalRecord` table as #3; add `ttl_seconds` and persist to SQLite
- `src/engine/registry.py` — register privileged tool calls that require an approval record before execution

**Note**: This is a natural extension of #3; implement together.

---

## My picks — spike next

**Top pick: #1 + #3 together** — Per-workspace skill namespacing (#1) unlocks a concrete product capability (workspace-specific tool sets) and is purely additive to `src/engine/skills.py`. Recurring work approvals (#3) is a ~30-line safety addition to `src/cron/scheduler.py` + `src/cron/store.py`. Both are low-risk, high-signal, and can ship in one small PR.

**Then: #2** — Structured agent questions in `src/gateway/protocol.py` changes the interaction model meaningfully; worth a focused spike once #1 is proven.

**Defer: #4** — Background sessions require significant refactoring of the session/runtime boundary. Good future investment but not the next spike.
