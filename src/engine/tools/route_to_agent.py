"""route_to_agent tool — delegates tasks from Chief to sub-agents.

This tool is ONLY given to the Chief Agent. When the Chief's LLM
detects a "suggestion moment" in the transcript, it calls this tool
to delegate to the appropriate sub-agent (software-engineer, doctor, etc.).

The actual execution is handled by the Orchestrator — this file just
defines the tool schema and creates the handler wrapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.engine.orchestrator import Orchestrator


# Tool definition in Anthropic tool format
TOOL_DEF: dict = {
    "name": "route_to_agent",
    "description": (
        "Delegate a task to a specialized sub-agent. "
        "Use this when the meeting conversation needs a specific type of help: "
        "terminology suggestions, design pattern advice, pro/con analysis, etc. "
        "The sub-agent will search the knowledge base, analyze the context, "
        "and return a detailed suggestion.\n\n"
        "Available agents:\n"
        "- software-engineer: AI/ML terminology, design patterns, system design, "
        "code review, interview prep\n"
        "- ai-educator: AI curriculum design, teaching plans, project scoping, "
        "resume guidance, adult learning adaptation, agent-learning roadmaps\n"
        "- doctor: Medical terminology, diagnosis patterns (future)\n\n"
        "Pass the relevant transcript context so the sub-agent understands "
        "what the meeting is about."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": (
                    "Target sub-agent persona ID. "
                    "One of: 'software-engineer', 'ai-educator', 'doctor'"
                ),
            },
            "task": {
                "type": "string",
                "description": (
                    "What the sub-agent should do. Be specific. "
                    "E.g., 'Suggest relevant AI terminology for this discussion "
                    "about making LLMs use company docs' or "
                    "'Analyze pros and cons of the proposed event sourcing approach'"
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Relevant meeting transcript and context. Include the recent "
                    "conversation that triggered this delegation."
                ),
            },
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional: skill names to activate on the sub-agent. "
                    "E.g., ['term-suggest', 'design-pattern-suggest']. "
                    "If omitted, all skills are available."
                ),
            },
        },
        "required": ["agent", "task"],
    },
}


def create_route_handler(orchestrator: Orchestrator):
    """Create the route_to_agent handler bound to an orchestrator instance.

    Returns an async callable that matches the tool handler signature.
    """
    async def handler(
        agent: str,
        task: str,
        context: str = "",
        skills: list[str] | None = None,
    ) -> str:
        return await orchestrator.route_to_agent(
            agent=agent,
            task=task,
            context=context,
            skills=skills,
        )

    return handler
