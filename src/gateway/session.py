"""Session lifecycle management.

Creates, pauses, resumes, and tears down meeting sessions,
each backed by a queue lane key and one or more registered agents.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from src.shared.logger import get_logger
from src.shared.types import SessionState
from src.engine.registry import AgentRegistry

logger = get_logger("lexicon.gateway.session")


def _lane_key(session_id: str, agent_id: str) -> str:
    """Build the queue lane key for a session + agent pair."""
    return f"session:{session_id}:{agent_id}"


class SessionManager:
    """Manages the full lifecycle of meeting sessions.

    Each session owns:
    - A ``SessionState`` Pydantic model.
    - A queue lane key used by ``CommandQueue`` to serialise agent runs.
    - One or more agents registered in the ``AgentRegistry``.
    """

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry
        self._sessions: dict[str, SessionState] = {}
        # session_id → list of agent IDs created for that session
        self._session_agents: dict[str, list[str]] = {}
        # session_id → primary lane key
        self._lane_keys: dict[str, str] = {}

    # ── queries ───────────────────────────────────────────────────

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def lane_key(self, session_id: str) -> str | None:
        return self._lane_keys.get(session_id)

    def list_sessions(self) -> list[SessionState]:
        return list(self._sessions.values())

    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.status == "active")

    # ── lifecycle ─────────────────────────────────────────────────

    def create_session(
        self,
        persona: str = "software-engineer",
        metadata: dict[str, Any] | None = None,
    ) -> SessionState:
        """Create a new session and register its agent(s)."""
        session_id = str(uuid.uuid4())
        agent_id = f"{persona}-{session_id[:8]}"

        # Create the agent runtime in the registry
        self._registry.create(agent_id=agent_id, persona=persona)

        # Build the lane key that CommandQueue will use
        lane = _lane_key(session_id, agent_id)

        state = SessionState(
            id=session_id,
            persona=persona,
            status="active",
            metadata=metadata or {},
        )

        self._sessions[session_id] = state
        self._session_agents[session_id] = [agent_id]
        self._lane_keys[session_id] = lane

        logger.info(
            f"Session created: {session_id} | persona={persona} | lane={lane}"
        )
        return state

    def end_session(self, session_id: str) -> SessionState | None:
        """End a session and clean up its agents."""
        state = self._sessions.get(session_id)
        if state is None:
            logger.warning(f"end_session called for unknown session {session_id}")
            return None

        state.status = "ended"
        state.ended_at = datetime.utcnow()

        # Remove agents from registry
        for agent_id in self._session_agents.pop(session_id, []):
            self._registry.remove(agent_id)

        self._lane_keys.pop(session_id, None)

        logger.info(f"Session ended: {session_id}")
        return state

    def pause_session(self, session_id: str) -> SessionState | None:
        """Pause an active session."""
        state = self._sessions.get(session_id)
        if state is None or state.status != "active":
            return state

        state.status = "paused"
        logger.info(f"Session paused: {session_id}")
        return state

    def resume_session(self, session_id: str) -> SessionState | None:
        """Resume a paused session."""
        state = self._sessions.get(session_id)
        if state is None or state.status != "paused":
            return state

        state.status = "active"
        logger.info(f"Session resumed: {session_id}")
        return state
