# OpenClaw Watch — 2026-10-31

> Covers releases since last-checked 2026-09-23. Previous baseline: stable `2026.5.27`, beta `2026.5.28-beta.2`.

---

## What shipped

| Channel | Version | Date | Headline |
|---|---|---|---|
| **Stable** | `2026.10.9` | 2026-10-29 | Workspace tool scoping, credential hygiene, agent disk-full recovery |
| **Extended-stable (gateway-only)** | `2026.9.36` | 2026-10-29 | Untrusted-input bounding, workspace restriction backport, astral-char text fix |
| **Beta** | `2026.10.10-beta.5` | 2026-10-30 | Cron slot recovery, streaming partial-tag robustness, security boundaries |

*Note: OpenClaw uses Year.Month.Build numbering (not Year.Month.Day). `2026.10.9` = October, 9th build.*

Source: [github.com/openclaw/openclaw/releases](https://github.com/openclaw/openclaw/releases)

---

## What's notable

### 1. Workspace-scoped tool access (`tools.fs.workspaceOnly`)
`2026.10.9` and `2026.9.36` both shipped `tools.fs.workspaceOnly` applied to Gateway-built tools. Tools instantiated by the gateway are now confined to the workspace root rather than having open filesystem access. This is an explicit security boundary at the tool layer, not just at the gateway routing layer.

### 2. Cron slot recovery after restarts
`2026.10.10-beta.5` introduced recovery of missed cron slots after a process restart. When the scheduler comes back up, it detects and re-fires slots that were missed during the outage window, rather than silently dropping them. The pattern is a persistent slot-log checked at startup.

### 3. Streaming partial-tag robustness
`2026.10.10-beta.5` fixed Gateway stalls caused by tool-call-like tokens or partial XML tags arriving mid-stream from the LLM. The fix adds a lookahead buffer that holds ambiguous tag-open fragments until they resolve as real tool calls or as plain text, preventing the parser from entering a hung state.

### 4. Untrusted-input bounding
`2026.9.36` bounded untrusted input across media metadata, mail parsing, TOML, URIs, and oversized JSON schemas. Each input type is validated and size-capped before being passed to downstream handlers — moving validation upstream to the ingestion boundary rather than leaving it to individual tools.

### 5. Credential hygiene at channel/CLI boundaries
`2026.10.9` kept `hooks.token` out of agent and CLI child environments, masked Google OAuth secrets in logs, and ensured MCP CLI output strips credentials. The pattern is explicit environment sanitization for all child-process and sub-agent spawns.

---

## What we can use in Lexicon

Ranked by **value / effort** (high value = directly applicable to a real pain point; low effort = small, self-contained change).

### 1. Workspace-scoped tool access — `src/engine/workspace.py` + `src/engine/tools/registry.py`
**Value: High | Effort: Low**

`src/engine/workspace.py` already defines a workspace root concept. `src/engine/tools/registry.py` instantiates tools without checking whether their file-path arguments are confined to that root. Adding a workspace-path guard to `ToolRegistry.resolve()` (or wrapping `vault_read`/`vault_write` at load time) directly mirrors OpenClaw's `tools.fs.workspaceOnly` and prevents a tool misconfiguration from escaping the vault boundary.

Files: `src/engine/workspace.py`, `src/engine/tools/registry.py`, `src/engine/tools/vault_read.py`, `src/engine/tools/vault_write.py`

### 2. Cron slot recovery — `src/cron/scheduler.py` + `src/cron/store.py`
**Value: High | Effort: Medium**

`src/cron/store.py` persists scheduled jobs but there is no startup reconciliation pass. On restart, jobs whose fire-time fell during the outage are silently skipped. Following OpenClaw's pattern: on `Scheduler.start()`, query the store for jobs where `next_run < now` and re-dispatch them (with a dedup guard on run-id) before entering the normal polling loop.

Files: `src/cron/scheduler.py`, `src/cron/store.py`

### 3. Streaming partial-tag robustness — `src/engine/runtime.py` + `src/engine/llm/provider.py`
**Value: Medium | Effort: Medium**

`src/engine/runtime.py` streams LLM output and parses tool-call tokens inline. A partial `<tool_call` arriving at a chunk boundary can stall the parser. Adding a small lookahead buffer (hold chunks until a tag opens and closes, or until a non-tag character follows `<`) eliminates the hung-stream failure mode. `src/engine/llm/provider.py` is the right layer for the buffer since it sits between the raw stream and the runtime parser.

Files: `src/engine/runtime.py`, `src/engine/llm/provider.py`

### 4. Untrusted-input bounding — `src/gateway/protocol.py` + `src/engine/tools/rss_fetch.py`
**Value: Medium | Effort: Low-Medium**

`src/gateway/protocol.py` receives incoming messages (including media payloads) with no documented size cap. `src/engine/tools/rss_fetch.py` and `src/engine/tools/paper_fetch.py` pass external content downstream with no schema-size guard. Applying max-byte caps and schema-depth limits at `protocol.py` decode time and at each fetch-tool return mirrors OpenClaw's upstream bounding approach.

Files: `src/gateway/protocol.py`, `src/engine/tools/rss_fetch.py`, `src/engine/tools/paper_fetch.py`

### 5. Credential hygiene at spawn boundaries — `src/engine/runner.py`
**Value: Medium | Effort: Low**

`src/engine/runner.py` spawns sub-agents and skill subprocesses. Following OpenClaw's pattern, the environment dict passed to each child should explicitly exclude any credential or token keys (e.g., `LEXICON_API_KEY`, `VAULT_TOKEN`, `OPENAI_API_KEY`) that the child has no legitimate reason to inherit. A one-time allowlist of safe env vars at spawn time is low-effort and high confidence.

Files: `src/engine/runner.py`

---

## My picks to spike next

1. **Workspace-scoped tool access** (`src/engine/tools/registry.py`) — highest value-to-effort ratio; one guard function prevents an entire class of path-traversal bugs with no API change.
2. **Cron slot recovery** (`src/cron/scheduler.py`) — Lexicon's scheduled digests (openclaw-watch included) currently have no protection against missed fires; a startup reconciliation pass is a small, testable addition.
3. **Credential hygiene at spawn** (`src/engine/runner.py`) — lowest effort on the list; a single env-allowlist dict prevents token leakage into skill subprocesses.
