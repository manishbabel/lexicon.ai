"""FastAPI application — WebSocket gateway + REST endpoints.

The server is the entry point for the entire backend:
1. Creates all services (registry, queue, runner, sessions, router)
2. Exposes a WebSocket endpoint for real-time communication
3. Exposes REST endpoints for settings, health, etc.

Start with:
    uvicorn src.gateway.server:app --host 127.0.0.1 --port 18800
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.shared.constants import GATEWAY_HOST, GATEWAY_PORT
from src.shared.logger import get_logger
from src.shared.types import AgentOutput

from src.cron import CronScheduler
from src.engine.hooks.builtin import register_builtin_hooks
from src.engine.hooks.registry import trigger_hook
from src.engine.memory.short_term import ShortTermMemory
from src.engine.orchestrator import Orchestrator
from src.engine.queue import CommandQueue, QueueMode
from src.engine.registry import AgentRegistry
from src.engine.runner import AgentRunner
from src.engine.tools.setup import setup_tools

from .protocol import (
    ConnectMessage,
    ErrorMessage,
    SuggestionCategory,
    SuggestionStreamMessage,
)
from .router import MessageRouter
from .session import SessionManager

logger = get_logger("lexicon.gateway.server")


# ── Service singletons (created at startup) ──────────────────────

_registry: AgentRegistry | None = None
_queue: CommandQueue | None = None
_runner: AgentRunner | None = None
_sessions: SessionManager | None = None
_router: MessageRouter | None = None
_cron: CronScheduler | None = None
_orchestrator: Orchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, clean up on shutdown."""
    global _registry, _queue, _runner, _sessions, _router, _cron, _orchestrator

    logger.info("Starting Lexicon.ai gateway...")

    # 0. Register built-in hooks
    register_builtin_hooks()

    # 1. Tool registry (all tools available to sub-agents)
    _tool_registry = setup_tools()
    logger.info(f"Loaded {len(_tool_registry.list_tools())} tools: {_tool_registry.list_tools()}")

    # 2. Agent registry (creates AgentRuntime instances with tools wired)
    _registry = AgentRegistry(tool_registry=_tool_registry)
    _orchestrator = Orchestrator(llm=None, tool_registry=_tool_registry)

    # 2. Command queue (needs a run handler — set after runner is created)
    _runner_placeholder = None

    def _make_queue():
        # Temporary: create queue, then wire runner
        q = CommandQueue(run_handler=lambda run: asyncio.sleep(0))
        return q

    _queue = _make_queue()

    # 3. Runner (bridge between queue and agent runtime)
    _runner = AgentRunner(registry=_registry, queue=_queue)
    # Wire the actual run handler into the queue
    _queue._run_handler = _runner.handle_run

    # 4. Session manager
    _sessions = SessionManager(registry=_registry)

    # 5. Message router
    _router = MessageRouter(
        sessions=_sessions,
        queue=_queue,
        orchestrator=_orchestrator,
    )

    # Start the queue
    await _queue.start()

    # 6. Cron scheduler
    _cron = CronScheduler()

    # System handler: prune expired short-term memory (no LLM needed)
    async def _system_prune_memory() -> None:
        from src.shared.constants import SESSIONS_DIR
        total = 0
        if SESSIONS_DIR.exists():
            for agent_dir in SESSIONS_DIR.iterdir():
                if agent_dir.is_dir():
                    st = ShortTermMemory(agent_id=agent_dir.name)
                    total += st.prune()
        if total:
            logger.info(f"System prune: removed {total} expired memory entries")

    _cron.register_system_handler("__system:prune_memory", _system_prune_memory)

    # Enqueue function: cron jobs create agent runs via the command queue
    async def _cron_enqueue(agent: str, command: str, skill: str | None = None) -> None:
        session_key = f"cron:{agent}"
        prompt = command
        if skill:
            prompt = f"[SKILL HINT: {skill}] {command}"
        await _queue.enqueue(
            session_key=session_key,
            content=prompt,
            mode=QueueMode.COLLECT,
            lane="main",
        )

    _cron.set_enqueue_fn(_cron_enqueue)

    await _cron.start()

    await trigger_hook("gateway:start")
    logger.info(f"Gateway ready on ws://{GATEWAY_HOST}:{GATEWAY_PORT}/ws")

    yield

    # Shutdown
    await trigger_hook("gateway:stop")
    logger.info("Shutting down gateway...")
    await _cron.stop()
    await _queue.stop()


# ── FastAPI app ──────────────────────────────────────────────────

app = FastAPI(
    title="Lexicon.ai Gateway",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Localhost only in practice
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket endpoint ───────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Main WebSocket connection handler.

    Flow:
    1. Accept connection
    2. Wait for connect message → create session
    3. Register output listener (agent output → WS)
    4. Enter message loop: parse → route → respond
    5. On disconnect → clean up session
    """
    await ws.accept()
    conn_id = str(uuid.uuid4())[:8]
    logger.info(f"WS connected [{conn_id}]")

    session_id: str | None = None
    lane_key: str | None = None
    suggestion_counter = [0]
    # Accumulate full agent response, then split into category cards on "done"
    current_text_buffer = [""]

    import re as _re

    # Category detection: header pattern → frontend category
    CATEGORY_HEADERS: list[tuple[str, str]] = [
        ("terms you can use", "term"),
        ("term suggest", "term"),
        ("term explainer", "term"),
        ("key insight", "insight"),
        ("insight", "insight"),
        ("pro-con", "procon"),
        ("pro / con", "procon"),
        ("pros and cons", "procon"),
        ("design pattern", "pattern"),
        ("pattern suggest", "pattern"),
        ("ask this", "question"),
        ("smart question", "question"),
        ("question", "question"),
    ]

    def _split_into_cards(full_text: str) -> list[tuple[str, str]]:
        """Split agent response into (category, text) pairs by **Header**: sections.

        Returns a list of cards. Each card is (frontend_category, card_text).
        If no headers detected, returns one "general" card.
        """
        # Split on lines starting with ** (markdown bold headers)
        # Pattern: **Some Header**: rest of content
        sections: list[tuple[str, str]] = []
        # Split by bold header lines like "**Terms You Can Use**:" or "**Design Pattern Suggestion**:"
        parts = _re.split(r'(?=\*\*[^*]+\*\*\s*:)', full_text.strip())

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Try to extract the header
            header_match = _re.match(r'\*\*([^*]+)\*\*\s*:?\s*(.*)', part, _re.DOTALL)
            if header_match:
                header_text = header_match.group(1).strip().lower()
                body = header_match.group(2).strip()

                # Map header to frontend category
                category = "general"
                for pattern, cat in CATEGORY_HEADERS:
                    if pattern in header_text:
                        category = cat
                        break

                if body:
                    sections.append((category, body))
            else:
                # No header — general card
                if part:
                    sections.append(("general", part))

        if not sections:
            sections.append(("general", full_text.strip()))

        return sections

    async def _send_agent_output(output: AgentOutput) -> None:
        """Accumulate agent text, split into category cards on done."""

        if output.type == "text_delta":
            current_text_buffer[0] += output.delta

        elif output.type == "tool_result":
            logger.debug(f"Tool result [{conn_id}]: {output.tool_name}")

        elif output.type == "done":
            # Split accumulated text into category cards
            full_text = current_text_buffer[0]
            cards = _split_into_cards(full_text)

            for category, card_text in cards:
                sid = f"{conn_id}-{suggestion_counter[0]}"
                suggestion_counter[0] += 1

                # Send entire card as one delta + done (not streaming)
                msg = SuggestionStreamMessage(
                    session_id=session_id or "",
                    suggestion_id=sid,
                    category=category,
                    delta=card_text,
                )
                await ws.send_json(msg.model_dump(mode="json"))

                done_msg = SuggestionStreamMessage(
                    session_id=session_id or "",
                    suggestion_id=sid,
                    category=category,
                    done=True,
                )
                await ws.send_json(done_msg.model_dump(mode="json"))

            logger.info(
                f"Agent response split into {len(cards)} cards: "
                f"{[c[0] for c in cards]}"
            )
            current_text_buffer[0] = ""

        elif output.type == "error":
            logger.error(f"Agent error [{conn_id}]: {output.error}")
            err = ErrorMessage(code="agent_error", detail=output.error or "Unknown error")
            await ws.send_json(err.model_dump(mode="json"))

    try:
        while True:
            raw = await ws.receive_json()
            logger.debug(f"WS recv [{conn_id}]: {raw.get('type', '?')}")

            try:
                msg = _router.parse(raw)
            except Exception as e:
                err = ErrorMessage(code="parse_error", detail=str(e))
                await ws.send_json(err.model_dump(mode="json"))
                continue

            # Dispatch and send responses
            responses = await _router.dispatch(session_id, msg)

            for resp in responses:
                data = resp.model_dump(mode="json")
                await ws.send_json(data)

                # If we just connected, capture session_id and wire output listener
                if isinstance(msg, ConnectMessage) and hasattr(resp, "session_id"):
                    session_id = resp.session_id
                    lane_key = _sessions.lane_key(session_id)
                    if lane_key:
                        _runner.on_output(lane_key, _send_agent_output)
                    logger.info(
                        f"WS [{conn_id}] bound to session {session_id}"
                    )

    except WebSocketDisconnect:
        logger.info(f"WS disconnected [{conn_id}]")
    except Exception as e:
        logger.error(f"WS error [{conn_id}]: {e}")
    finally:
        # Clean up
        if lane_key:
            _runner.remove_output_listeners(lane_key)
        if session_id:
            _sessions.end_session(session_id)
        logger.info(f"WS cleanup done [{conn_id}]")


# ── REST endpoints ───────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "lexicon-gateway"}


@app.get("/sessions")
async def list_sessions():
    """List all active sessions (for debugging / dashboard)."""
    sessions = _sessions.list_sessions() if _sessions else []
    return {"sessions": [s.model_dump(mode="json") for s in sessions]}


@app.get("/queue/status")
async def queue_status():
    """Show active runs and queue state (for debugging)."""
    if not _queue:
        return {"active_runs": {}}
    runs = _queue.get_active_runs()
    return {
        "active_runs": {
            k: {"id": v.id, "phase": v.phase.value}
            for k, v in runs.items()
        }
    }


@app.get("/cron/jobs")
async def cron_jobs():
    """List all cron jobs and their state."""
    if not _cron:
        return {"jobs": []}
    jobs = _cron.list_jobs(include_disabled=True)
    return {
        "jobs": [j.model_dump(mode="json") for j in jobs]
    }


@app.post("/cron/run/{job_id}")
async def cron_run_now(job_id: str):
    """Trigger a cron job immediately."""
    if not _cron:
        return {"error": "Cron not initialized"}
    job = _cron.get_job(job_id)
    if not job:
        return {"error": f"Job not found: {job_id}"}
    await _cron.run_now(job_id)
    return {"status": "triggered", "job_id": job_id}


@app.get("/api/deepgram-key")
async def get_deepgram_key():
    """Return Deepgram API key for browser audio capture. Localhost only."""
    from src.shared.config import get_settings as _get_settings
    key = _get_settings().deepgram_api_key
    if not key:
        return {"key": ""}
    return {"key": key}


@app.get("/api/settings")
async def get_settings():
    """Return current settings (API keys masked)."""
    import json
    from src.shared.constants import CONFIG_PATH

    config: dict = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, KeyError):
            pass

    def mask(key: str) -> str:
        val = config.get(key, "")
        if not val or len(val) < 8:
            return ""
        return val[:4] + "..." + val[-4:]

    return {
        "openai_api_key": mask("openai_api_key"),
        "anthropic_api_key": mask("anthropic_api_key"),
        "deepgram_api_key": mask("deepgram_api_key"),
        "default_llm_provider": config.get("default_llm_provider", "openai"),
        "default_llm_model": config.get("default_llm_model", "gpt-4o"),
        "chief_llm_provider": config.get("chief_llm_provider", ""),
        "chief_llm_model": config.get("chief_llm_model", ""),
        "software_engineer_llm_provider": config.get("software_engineer_llm_provider", ""),
        "software_engineer_llm_model": config.get("software_engineer_llm_model", ""),
        "log_level": config.get("log_level", "INFO"),
        "has_openai_key": bool(config.get("openai_api_key")),
        "has_anthropic_key": bool(config.get("anthropic_api_key")),
        "has_deepgram_key": bool(config.get("deepgram_api_key")),
    }


@app.post("/api/settings")
async def update_settings(body: dict):
    """Update settings. Only provided fields are changed."""
    import json
    from src.shared.constants import CONFIG_PATH
    from src.shared.config import _settings

    # Load existing
    config: dict = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, KeyError):
            pass

    # Allowed fields
    allowed = {
        "openai_api_key", "anthropic_api_key", "deepgram_api_key",
        "default_llm_provider", "default_llm_model",
        "chief_llm_provider", "chief_llm_model",
        "software_engineer_llm_provider", "software_engineer_llm_model",
        "log_level",
    }

    for key, val in body.items():
        if key in allowed and val is not None:
            config[key] = val

    # Save
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))

    # Reload singleton
    import src.shared.config as cfg_mod
    cfg_mod._settings = None

    return {"ok": True}
