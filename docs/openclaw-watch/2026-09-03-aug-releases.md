# OpenClaw Watch — 2026-09-03

## What Shipped

| Version | Date | Type | Headline |
|---|---|---|---|
| **2026.8.2** | 2026-09-01 | Stable | Desktop companion, background session creation, upgrade-safe config preservation |
| **2026.8.1** | 2026-08-31 | Stable | Conversation search, cloud workers, recurring-work approval, structured agent responses, private credential requests |
| **2026.8.1-beta.4** | 2026-08-28 | Beta | Gateway restart recovery, worker recovery, Codex runtime 0.150.1 |

Previous tracked versions: stable `2026.5.27`, beta `2026.5.28-beta.2` (baseline — first state).

### 2026.8.1 headline changes
- Conversation search by exact words and phrases across history
- Sessions on paired devices and cloud workers
- Durable session progress cards across reloads
- Structured agent question responses via cards/buttons
- Interactive widgets and dashboard pins
- **Private credential requests** without exposing values in context
- **Recurring work approval permissions** — gates for scheduled/automated tasks
- Enhanced media attachment across uploads and playback

### 2026.8.2 headline changes
- Home agent dock positioning
- Linux desktop companion (AppImage + .deb)
- **Background session creation** without page switching
- **Enhanced upgrade safety** with configuration preservation
- Improved voice reliability
- Four new UI themes (CRT, Manuscript, Rosé, Miami)

### 2026.8.1-beta.4 headline changes
- **Gateway restart recovery** for in-flight admitted turns
- Config-write reliability improvements
- Codex runtime bumped to 0.150.1
- Worker recovery and control-UI file safety
- Model-browsing reliability after plugin activation

---

## What's Notable

### 1. Recurring Work Approval Permissions (2026.8.1)
Scheduled and automated tasks now support an approval gate before execution. The pattern: before a recurring job fires, the runtime checks for a pending approval record; if absent or expired, the job is held and the operator is notified. This directly addresses the risk of unchecked autonomous cron execution — a pattern gap in most agent frameworks.

### 2. Gateway Restart Recovery for Admitted Turns (2026.8.1-beta.4)
When the gateway restarts mid-session, turns that had already been admitted (session established, turn in flight) can now be recovered. The approach is to journal admitted turns to durable storage before processing, allowing the gateway to replay or resume them on restart. Pure reliability engineering but architecturally significant for production deployments.

### 3. Exact-Phrase Conversation Search (2026.8.1)
OpenClaw added literal keyword/phrase search over conversation history, complementing its existing semantic/vector search. The two retrieval modes are unified under a single query interface with mode selection. This improves recall precision in cases where semantic search overfits to meaning while missing the specific wording an operator needs.

### 4. Private Credential Requests Without Context Exposure (2026.8.1)
Agents can now request sensitive values (API keys, passwords) through a typed protocol message that never surfaces the value in the conversation transcript or context window. The credential flows through a side-channel to the runtime, which injects it into the tool call environment directly.

### 5. Background Session Creation (2026.8.2)
Sessions can be created asynchronously in the background without blocking the current interaction. This decouples session initialization (which may involve provider handshakes, memory hydration, and workspace load) from the first user turn, reducing perceived latency.

---

## What We Can Use in Lexicon

Ranked by value/effort (H=High, M=Medium, L=Low).

| # | Pattern | Value | Effort | Lexicon file(s) |
|---|---|---|---|---|
| 1 | Recurring work approval gate | H | M | `src/cron/scheduler.py`, `src/cron/store.py` |
| 2 | Transcript exact-phrase search | H | L | `src/engine/memory/search.py`, `src/engine/memory/transcript_index.py` |
| 3 | Gateway restart recovery (turn journaling) | H | H | `src/gateway/server.py`, `src/gateway/session.py` |
| 4 | Private credential requests | M | L | `src/gateway/protocol.py` |
| 5 | Structured agent response types (cards/buttons) | M | M | `src/gateway/protocol.py`, `src/gateway/session.py` |

### Detail

**1. Recurring work approval gate** (`src/cron/scheduler.py`, `src/cron/store.py`)
Before `scheduler.py` fires a job, check `store.py` for a pending approval record keyed on the job ID. If none exists or it is expired, hold the job and surface a notification. This is a one-shot addition to the dispatch loop in the scheduler and a new approval-state record type in the store. High value because Lexicon already has a real cron module with no human-in-the-loop guardrail on automated runs.

**2. Transcript exact-phrase search** (`src/engine/memory/search.py`, `src/engine/memory/transcript_index.py`)
`transcript_index.py` already exists. Add a `mode` parameter to the search interface in `search.py` that switches between `semantic` (current) and `exact` (substring/regex over indexed transcript text). Zero new dependencies if done with simple string matching; can upgrade to an inverted-index approach later. Complements the existing vector path rather than replacing it.

**3. Gateway restart recovery** (`src/gateway/server.py`, `src/gateway/session.py`)
Before processing an admitted turn, write a journal entry (turn ID, session state, timestamp) via `session.py`. On `server.py` startup, scan the journal for incomplete turns and re-admit them. High effort because it requires deciding on journal storage, conflict handling, and idempotency — but the pattern is well-understood.

**4. Private credential requests** (`src/gateway/protocol.py`)
Add a `credential_request` message type to the protocol. The gateway intercepts this type and routes the credential value through an out-of-band channel (env injection or a secrets store call) rather than returning it in the normal turn response. Low effort to stub out the protocol type; the injection mechanism depends on how Lexicon's runtime is configured.

**5. Structured response types** (`src/gateway/protocol.py`, `src/gateway/session.py`)
Extend the protocol with a `structured_response` turn type carrying a schema (cards, buttons, form fields). `session.py` would deserialize these into typed objects rather than raw text. Medium effort; most value comes if Lexicon has a UI layer that can render them.

---

## Spike Picks

**Primary: Recurring work approval gate** — Lexicon's cron module fires autonomously with no approval mechanism. The `scheduler.py` + `store.py` pair already provides the right hook points. A spike could be as small as adding an `approval_required` flag to job definitions in `store.py` and a pre-dispatch check in `scheduler.py`. One PR, observable safety win.

**Secondary: Transcript exact-phrase search** — `transcript_index.py` exists and is the right place. Adding a mode flag to `search.py` is a one-afternoon change that immediately improves retrieval precision for debugging and memory queries.
