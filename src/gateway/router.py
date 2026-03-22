"""Message router — dispatches WebSocket frames to the right handler.

Each ``ClientMessage.type`` maps to a handler method that knows
how to process it (enqueue transcript, control meeting, query memory, etc.).

The router does NOT own business logic — it translates protocol messages
into calls on SessionManager, CommandQueue, and other services.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import TypeAdapter

from src.engine.hooks.registry import trigger_hook
from src.shared.logger import get_logger

from .protocol import (
    AgentPromptMessage,
    AgentReplyMessage,
    ClientMessage,
    ConnectedMessage,
    ConnectMessage,
    ErrorMessage,
    MeetingControlMessage,
    MeetingPrepareMessage,
    MeetingPreparedMessage,
    MeetingStateMessage,
    MemoryQueryMessage,
    PersonaSelectMessage,
    ServerMessage,
    SuggestionCategory,
    TermFeedbackMessage,
    TranscriptAckMessage,
    TranscriptChunkMessage,
)
from .session import SessionManager
from src.engine.queue import CommandQueue, QueueMode
from src.engine.orchestrator import Orchestrator

logger = get_logger("lexicon.gateway.router")

# Pydantic adapter for parsing the discriminated union
_client_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


class MessageRouter:
    """Routes inbound WebSocket messages to the appropriate handler.

    Stateless per-message — all state lives in SessionManager and CommandQueue.

    Usage:
        router = MessageRouter(sessions=session_mgr, queue=cmd_queue)
        msg = router.parse(raw_json)
        responses = await router.dispatch(session_id, msg)
        for resp in responses:
            await ws.send_json(resp.model_dump())
    """

    def __init__(
        self,
        sessions: SessionManager,
        queue: CommandQueue,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        self._sessions = sessions
        self._queue = queue
        self._orchestrator = orchestrator

    # ── Parse ────────────────────────────────────────────────────

    def parse(self, data: dict[str, Any]) -> ClientMessage:
        """Parse a raw JSON dict into a typed ClientMessage.

        Raises ValueError if the message type is unknown or validation fails.
        """
        return _client_adapter.validate_python(data)

    # ── Dispatch ─────────────────────────────────────────────────

    async def dispatch(
        self,
        session_id: str | None,
        msg: ClientMessage,
    ) -> list[ServerMessage]:
        """Route a parsed message to its handler. Returns response messages.

        session_id is None only for ConnectMessage (first message on WS).
        All other messages require an active session.
        """
        if isinstance(msg, ConnectMessage):
            return self._handle_connect(msg)

        # All other messages need a session
        if session_id is None:
            return [ErrorMessage(code="no_session", detail="Send connect first")]

        session = self._sessions.get(session_id)
        if session is None:
            return [ErrorMessage(code="no_session", detail=f"Unknown session {session_id}")]

        if isinstance(msg, TranscriptChunkMessage):
            return await self._handle_transcript(session_id, msg)
        elif isinstance(msg, MeetingControlMessage):
            return await self._handle_meeting_control(session_id, msg)
        elif isinstance(msg, MeetingPrepareMessage):
            return await self._handle_meeting_prepare(session_id, msg)
        elif isinstance(msg, PersonaSelectMessage):
            return self._handle_persona_select(session_id, msg)
        elif isinstance(msg, MemoryQueryMessage):
            return await self._handle_memory_query(session_id, msg)
        elif isinstance(msg, TermFeedbackMessage):
            return await self._handle_term_feedback(session_id, msg)
        elif isinstance(msg, AgentPromptMessage):
            return await self._handle_agent_prompt(session_id, session, msg)
        else:
            return [ErrorMessage(code="unknown_type", detail=f"Unhandled message type")]

    # ── Handlers ─────────────────────────────────────────────────

    def _handle_connect(self, msg: ConnectMessage) -> list[ServerMessage]:
        """Create a session and return connection confirmation."""
        session = self._sessions.create_session(
            persona=msg.persona,
            metadata=msg.metadata,
        )
        lane_key = self._sessions.lane_key(session.id) or ""
        logger.info(f"Client connected: session={session.id} persona={msg.persona}")

        return [ConnectedMessage(
            session_id=session.id,
            persona=session.persona,
            queue_lane=lane_key,
        )]

    async def _handle_transcript(
        self,
        session_id: str,
        msg: TranscriptChunkMessage,
    ) -> list[ServerMessage]:
        """Enqueue a transcript chunk for the agent.

        Non-final (interim) results are dropped — we only process
        Deepgram's final transcript chunks to avoid noise.
        """
        if not msg.is_final:
            return []

        lane_key = self._sessions.lane_key(session_id)
        if not lane_key:
            return [ErrorMessage(code="no_lane", detail="Session has no queue lane")]

        # Build content with optional speaker label
        content = msg.text
        if msg.speaker:
            content = f"[{msg.speaker}]: {msg.text}"

        message_id = await self._queue.enqueue(
            session_key=lane_key,
            content=content,
            mode=msg.mode,
            lane="main",
        )

        # Fire transcript hook
        await trigger_hook("transcript:chunk", {
            "session_id": session_id,
            "text": msg.text,
            "speaker": msg.speaker or "",
            "meeting_id": session_id,  # session_id doubles as meeting_id
        })

        depth = self._queue.get_queue_depth(lane_key)
        return [TranscriptAckMessage(message_id=message_id, queue_depth=depth)]

    async def _handle_meeting_control(
        self,
        session_id: str,
        msg: MeetingControlMessage,
    ) -> list[ServerMessage]:
        """Start, pause, or stop a meeting session."""
        if msg.action == "start":
            state = self._sessions.resume_session(session_id)
            if state is None:
                state = self._sessions.get(session_id)
        elif msg.action == "pause":
            state = self._sessions.pause_session(session_id)
        elif msg.action == "stop":
            state = self._sessions.end_session(session_id)
        else:
            return [ErrorMessage(code="bad_action", detail=f"Unknown action: {msg.action}")]

        if state is None:
            return [ErrorMessage(code="no_session", detail="Session not found")]

        logger.info(f"Meeting {msg.action}: session={session_id} status={state.status}")

        # Fire meeting hook
        await trigger_hook(f"meeting:{msg.action}", {
            "session_id": session_id,
            "status": state.status,
            "queue": self._queue,
        })

        return [MeetingStateMessage(session_id=session_id, status=state.status)]

    async def _handle_meeting_prepare(
        self,
        session_id: str,
        msg: MeetingPrepareMessage,
    ) -> list[ServerMessage]:
        """Pre-meeting preparation — agent loads context before audio starts.

        Sends the prep context through the queue so the agent can:
        1. Search memory for relevant knowledge
        2. Load matching terms
        3. Build a meeting brief

        The actual prep work happens in the agent run. We just enqueue it
        with a structured prompt the agent understands.
        """
        lane_key = self._sessions.lane_key(session_id)
        if not lane_key:
            return [ErrorMessage(code="no_lane", detail="Session has no queue lane")]

        # Build a structured prep prompt for the agent
        parts = ["[PRE-MEETING PREPARATION]"]
        if msg.agenda:
            parts.append(f"Agenda: {msg.agenda}")
        if msg.topics:
            parts.append(f"Topics: {', '.join(msg.topics)}")
        if msg.attendees:
            parts.append(f"Attendees: {', '.join(msg.attendees)}")
        if msg.notes:
            parts.append(f"Notes: {msg.notes}")
        parts.append(
            "Search your memory and terms for relevant knowledge. "
            "Prepare a brief summary of key concepts, terms, and talking points "
            "I should know for this meeting."
        )

        await self._queue.enqueue(
            session_key=lane_key,
            content="\n".join(parts),
            mode=QueueMode.COLLECT,
            lane="main",
        )

        logger.info(f"Meeting prep enqueued: session={session_id} topics={msg.topics}")

        # The actual MeetingPreparedMessage will be sent by the runner
        # when the agent finishes its prep run. For now, ack the request.
        return []

    def _handle_persona_select(
        self,
        session_id: str,
        msg: PersonaSelectMessage,
    ) -> list[ServerMessage]:
        """Switch the persona for this session.

        Ends the current session agents and creates new ones with
        the requested persona. Session ID stays the same.
        """
        # End current agents
        self._sessions.end_session(session_id)

        # Create new session with the new persona (reuses session slot)
        new_session = self._sessions.create_session(
            persona=msg.persona,
        )

        lane_key = self._sessions.lane_key(new_session.id) or ""
        logger.info(f"Persona switched to {msg.persona}: new session={new_session.id}")

        return [ConnectedMessage(
            session_id=new_session.id,
            persona=new_session.persona,
            queue_lane=lane_key,
        )]

    async def _handle_memory_query(
        self,
        session_id: str,
        msg: MemoryQueryMessage,
    ) -> list[ServerMessage]:
        """Direct memory search — bypasses the agent queue.

        TODO: Wire to MemoryManager.search() when Phase 3 is built.
        For now returns a placeholder.
        """
        logger.info(f"Memory query: session={session_id} q={msg.query[:50]}")
        # Placeholder until memory system is wired
        return [ErrorMessage(
            code="not_implemented",
            detail="Memory query not yet implemented. Coming in Phase 3.",
        )]

    async def _handle_term_feedback(
        self,
        session_id: str,
        msg: TermFeedbackMessage,
    ) -> list[ServerMessage]:
        """Record that the user used or dismissed a suggested term.

        TODO: Wire to terms.bump_used() / terms.bump_dismissed() in Phase 3.
        """
        logger.info(
            f"Term feedback: session={session_id} "
            f"term={msg.term_id} action={msg.action}"
        )
        # Placeholder until term system is wired
        return []

    async def _handle_agent_prompt(
        self,
        session_id: str,
        session,
        msg: AgentPromptMessage,
    ) -> list[ServerMessage]:
        """Route a direct chat prompt to a sub-agent."""
        if self._orchestrator is None:
            return [ErrorMessage(
                code="no_orchestrator",
                detail="Sub-agent prompting is not available yet.",
            )]

        prompt = msg.prompt.strip()
        if not prompt:
            return [ErrorMessage(
                code="bad_agent_prompt",
                detail="Prompt cannot be empty.",
            )]

        try:
            routed_agent = self._resolve_prompt_agent(
                requested_agent=msg.agent,
                prompt=prompt,
                session_persona=session.persona,
            )
        except ValueError as exc:
            return [ErrorMessage(code="bad_agent_prompt", detail=str(exc))]

        skills = self._resolve_prompt_skills(
            agent=routed_agent,
            prompt=prompt,
            explicit_skills=msg.skills,
        )

        context = msg.context.strip()
        response = await self._orchestrator.route_to_agent(
            agent=routed_agent,
            task=prompt,
            context=context,
            skills=skills,
        )

        return [AgentReplyMessage(
            session_id=session_id,
            request_id=msg.request_id,
            requested_agent=msg.agent,
            routed_agent=routed_agent,
            response=response,
        )]

    def _resolve_prompt_agent(
        self,
        requested_agent: str,
        prompt: str,
        session_persona: str,
    ) -> str:
        """Choose which sub-agent should handle a direct UI prompt."""
        requested = (requested_agent or "auto").strip().lower()
        allowed_agents = {"software-engineer", "ai-educator", "doctor"}

        if requested != "auto":
            if requested not in allowed_agents:
                raise ValueError(
                    "Agent must be one of: auto, software-engineer, ai-educator, doctor."
                )
            return requested

        inferred = self._infer_agent_from_prompt(prompt)
        if inferred:
            return inferred

        if session_persona in allowed_agents:
            return session_persona

        return "software-engineer"

    def _infer_agent_from_prompt(self, prompt: str) -> str | None:
        text = prompt.lower()

        educator_keywords = {
            "adult learning",
            "bootcamp",
            "capstone",
            "career",
            "cohort",
            "course",
            "course outline",
            "curriculam",
            "curriculum",
            "curricular",
            "educat",
            "internship",
            "learner",
            "learning",
            "lesson",
            "module",
            "portfolio",
            "resume",
            "student",
            "students",
            "syllabus",
            "teach",
            "teaching",
            "training",
            "workshop",
        }
        doctor_keywords = {
            "clinical",
            "diagnosis",
            "doctor",
            "medical",
            "medicine",
            "patient",
            "symptom",
            "treatment",
        }

        if any(keyword in text for keyword in educator_keywords):
            return "ai-educator"
        if any(keyword in text for keyword in doctor_keywords):
            return "doctor"
        return None

    def _resolve_prompt_skills(
        self,
        agent: str,
        prompt: str,
        explicit_skills: list[str] | None,
    ) -> list[str] | None:
        skills = list(dict.fromkeys(explicit_skills or []))
        text = prompt.lower()

        if agent == "ai-educator":
            if any(keyword in text for keyword in ("curriculum", "curriculam", "course", "course outline", "bootcamp", "cohort", "module", "syllabus", "workshop")):
                skills.append("curriculum-architect")
            if any(keyword in text for keyword in ("adult", "manager", "professional", "workplace", "executive", "business")):
                skills.append("adult-learning-advisor")
            if any(keyword in text for keyword in ("resume", "portfolio", "internship", "job", "career", "linkedin")):
                skills.append("resume-studio")
            if any(keyword in text for keyword in ("capstone", "project", "prototype", "build", "client", "demo")):
                skills.append("live-project-mentor")
            if any(keyword in text for keyword in ("agent", "agents", "automation", "workflow", "orchestration")):
                skills.append("agent-readiness-roadmap")

        deduped = list(dict.fromkeys(skills))
        return deduped or None
