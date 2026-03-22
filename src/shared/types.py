"""Pydantic models shared across the application."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ── Agent ──────────────────────────────────────────────────────────

class AgentConfig(BaseModel):
    id: str
    workspace_path: str
    persona: str  # "chief", "software-engineer", "ai-educator", "doctor"
    provider: str = "openai"
    model: str = "gpt-4o"
    max_tokens: int = 1024


class WorkspaceContext(BaseModel):
    identity: str = ""  # IDENTITY.md content
    soul: str = ""  # SOUL.md content
    agent: str = ""  # AGENT.md content


# ── Messages ───────────────────────────────────────────────────────

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=_now)


# ── Memory ─────────────────────────────────────────────────────────

class MemoryEntry(BaseModel):
    id: str = Field(default_factory=_uuid)
    agent_id: str
    content: str
    summary: str | None = None
    category: str | None = None  # "design-pattern", "paper", "decision", "meeting-digest"
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    importance: float = 0.5
    access_count: int = 0
    last_accessed: datetime | None = None
    decay_score: float = 1.0
    source: str | None = None  # "meeting", "paper", "manual", "reflection"
    created_at: datetime = Field(default_factory=_now)
    # Search result fields (not stored)
    relevance: float = 0.0


class TermEntry(BaseModel):
    id: str = Field(default_factory=_uuid)
    term: str
    full_form: str | None = None
    definition: str
    use_in_sentence: str | None = None
    category: str  # "llm", "system-design", "mlops", "data-eng", "agents", "infra"
    difficulty: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    related_terms: list[str] = Field(default_factory=list)
    context_tags: list[str] = Field(default_factory=list)
    source: str = "preloaded"  # "preloaded", "learned", "paper:<url>"
    times_suggested: int = 0
    times_used_by_user: int = 0
    created_at: datetime = Field(default_factory=_now)
    # Search result fields
    relevance: float = 0.0


# ── Skills ─────────────────────────────────────────────────────────

class SkillTriggers(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)


class SkillDefinition(BaseModel):
    name: str
    description: str = ""
    triggers: SkillTriggers = Field(default_factory=SkillTriggers)
    instructions: str = ""  # Markdown body after frontmatter
    base_dir: str = ""
    source: Literal["bundled", "shared", "workspace"] = "bundled"


# ── Session ────────────────────────────────────────────────────────

class SessionState(BaseModel):
    id: str = Field(default_factory=_uuid)
    title: str | None = None
    persona: str = "software-engineer"
    status: Literal["active", "paused", "ended"] = "active"
    started_at: datetime = Field(default_factory=_now)
    ended_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Agent Output (streaming) ──────────────────────────────────────

class AgentOutput(BaseModel):
    type: Literal["text_delta", "tool_use", "tool_result", "done", "error"]
    delta: str = ""
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_result: Any = None
    error: str | None = None


# ── LLM Types ─────────────────────────────────────────────────────

class LLMEvent(BaseModel):
    type: Literal["text_delta", "tool_use", "stop"]
    text: str = ""
    name: str | None = None  # tool name
    input: dict[str, Any] | None = None  # tool input
    raw: Any = None  # original SDK object for message construction
