"""Pydantic message types for WebSocket communication.

Defines the Client→Gateway and Gateway→Client message schemas
using a discriminated union on the ``type`` field.

Suggestion categories drive the frontend card rendering:
- term_explain:  Someone used an unfamiliar term → explain it
- term_suggest:  Opportunity to use an impressive term → ready-to-use sentence
- pro_con:       Someone proposed a solution → pros, cons, what to mention
- design:        Architecture discussion → relevant pattern / approach
- question:      Good moment to ask a smart question
- fact_check:    Someone made a claim → confirm or add context
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Annotated, Literal, Union

from pydantic import BaseModel, Field

from src.engine.queue import QueueMode


# ── helpers ───────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.utcnow()


# ── Suggestion categories ─────────────────────────────────────────

class SuggestionCategory(str, Enum):
    """What kind of real-time output the agent is producing.

    The frontend renders each category differently (icon, color, layout).
    The agent sets this based on what's happening in the meeting.
    """

    TERM_EXPLAIN = "term_explain"
    """Someone used a term → explain what it means."""

    TERM_SUGGEST = "term_suggest"
    """Opportunity to drop an impressive term → includes ready-to-use sentence."""

    PRO_CON = "pro_con"
    """Someone proposed a solution → pros, cons, what to say."""

    DESIGN = "design"
    """Architecture discussion → suggest a pattern or approach."""

    QUESTION = "question"
    """Good moment to ask a smart question."""

    FACT_CHECK = "fact_check"
    """Someone made a claim → confirm, correct, or add context."""

    GENERAL = "general"
    """Catch-all for suggestions that don't fit other categories."""


# ── Client → Gateway messages ────────────────────────────────────

class ConnectMessage(BaseModel):
    """Initial handshake sent by the client after WS open."""

    type: Literal["connect"] = "connect"
    persona: str = "software-engineer"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranscriptChunkMessage(BaseModel):
    """A chunk of live transcript text from the client.

    The browser receives this from Deepgram (client-side STT)
    and forwards it to the gateway. Speaker label comes from
    Deepgram's diarization.
    """

    type: Literal["transcript.chunk"] = "transcript.chunk"
    text: str
    is_final: bool = True
    mode: QueueMode = QueueMode.STEER
    speaker: str | None = None
    timestamp: datetime = Field(default_factory=_now)


class PersonaSelectMessage(BaseModel):
    """Client requests a persona change mid-session."""

    type: Literal["persona.select"] = "persona.select"
    persona: str


class MeetingControlMessage(BaseModel):
    """Start / pause / stop the meeting session."""

    type: Literal["meeting.control"] = "meeting.control"
    action: Literal["start", "pause", "stop"]


class MeetingPrepareMessage(BaseModel):
    """Pre-meeting context so the agent can prepare before audio starts.

    Send this before clicking Start. The agent will:
    1. Search long-term memory for relevant knowledge
    2. Load matching terms from the terms table
    3. Pre-activate relevant skills
    4. Build a meeting brief ready for real-time use
    """

    type: Literal["meeting.prepare"] = "meeting.prepare"
    agenda: str = ""
    topics: list[str] = Field(default_factory=list)
    attendees: list[str] = Field(default_factory=list)
    notes: str = ""


class MemoryQueryMessage(BaseModel):
    """Client asks for a direct memory lookup (bypasses the queue)."""

    type: Literal["memory.query"] = "memory.query"
    query: str
    top_k: int = 5


class TermFeedbackMessage(BaseModel):
    """Client marks a suggested term as 'used' in the meeting.

    This feeds the term intelligence loop: terms the user actually
    uses get boosted, terms they ignore get deprioritized.
    """

    type: Literal["term.feedback"] = "term.feedback"
    term_id: str
    action: Literal["used", "dismissed"]


class AgentPromptMessage(BaseModel):
    """Direct instruction to a sub-agent from the UI chat panel."""

    type: Literal["agent.prompt"] = "agent.prompt"
    request_id: str
    prompt: str
    agent: str = "auto"
    context: str = ""
    skills: list[str] = Field(default_factory=list)


# Discriminated union of all inbound messages
ClientMessage = Annotated[
    Union[
        ConnectMessage,
        TranscriptChunkMessage,
        PersonaSelectMessage,
        MeetingControlMessage,
        MeetingPrepareMessage,
        MemoryQueryMessage,
        TermFeedbackMessage,
        AgentPromptMessage,
    ],
    Field(discriminator="type"),
]


# ── Gateway → Client messages ────────────────────────────────────

class ConnectedMessage(BaseModel):
    """Acknowledgement of a successful connect handshake."""

    type: Literal["connected"] = "connected"
    session_id: str
    persona: str
    queue_lane: str


class SuggestionStreamMessage(BaseModel):
    """Streaming suggestion / agent output pushed to the client.

    Each suggestion has a category so the frontend can render it
    with the right icon, color, and layout. The suggestion_id groups
    deltas belonging to the same suggestion card.
    """

    type: Literal["suggestion.stream"] = "suggestion.stream"
    session_id: str
    suggestion_id: str = ""
    category: str = "general"
    delta: str = ""
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_result: Any = None
    done: bool = False


class TermSuggestMessage(BaseModel):
    """Dedicated term suggestion with ready-to-use sentence.

    Separate from SuggestionStream because terms have structured
    fields the frontend renders as a compact card.
    """

    type: Literal["term.suggest"] = "term.suggest"
    session_id: str
    term_id: str
    term: str
    definition: str
    use_in_sentence: str = ""
    category: str = ""
    difficulty: str = "intermediate"
    related_terms: list[str] = Field(default_factory=list)


class TranscriptAckMessage(BaseModel):
    """Immediate acknowledgement that a transcript chunk was enqueued."""

    type: Literal["transcript.ack"] = "transcript.ack"
    message_id: str
    queue_depth: int = 0


class MeetingStateMessage(BaseModel):
    """Broadcast whenever the meeting state changes."""

    type: Literal["meeting.state"] = "meeting.state"
    session_id: str
    status: Literal["active", "paused", "ended"]


class MeetingPreparedMessage(BaseModel):
    """Server confirms pre-meeting preparation is complete.

    Includes a summary of what was loaded so the user knows
    the agent is ready.
    """

    type: Literal["meeting.prepared"] = "meeting.prepared"
    session_id: str
    terms_loaded: int = 0
    memories_loaded: int = 0
    summary: str = ""


class ErrorMessage(BaseModel):
    """Error pushed to the client."""

    type: Literal["error"] = "error"
    code: str = "internal"
    detail: str = ""


class AgentReplyMessage(BaseModel):
    """Response from a directly prompted sub-agent."""

    type: Literal["agent.reply"] = "agent.reply"
    session_id: str
    request_id: str
    requested_agent: str
    routed_agent: str
    response: str


# Discriminated union of all outbound messages
ServerMessage = Annotated[
    Union[
        ConnectedMessage,
        SuggestionStreamMessage,
        TermSuggestMessage,
        TranscriptAckMessage,
        MeetingStateMessage,
        MeetingPreparedMessage,
        AgentReplyMessage,
        ErrorMessage,
    ],
    Field(discriminator="type"),
]
