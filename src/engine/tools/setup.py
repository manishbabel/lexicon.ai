"""Tool setup — register all available tools into a ToolRegistry.

Call setup_tools() to get a fully loaded registry, then wire it into any runtime.
Call setup_chief_tools() to create a registry with route_to_agent for the Chief.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .paper_fetch import TOOL_DEF as PAPER_FETCH_DEF
from .paper_fetch import paper_fetch
from .qmd_search import TOOL_DEF as QMD_SEARCH_DEF
from .qmd_search import qmd_search
from .registry import ToolRegistry
from .route_to_agent import TOOL_DEF as ROUTE_DEF
from .route_to_agent import create_route_handler
from .rss_fetch import TOOL_DEF as RSS_FETCH_DEF
from .rss_fetch import rss_fetch
from .term_feedback import TOOL_DEF as TERM_FEEDBACK_DEF
from .term_feedback import term_feedback
from .vault_read import TOOL_DEF as VAULT_READ_DEF
from .vault_read import vault_read
from .vault_write import TOOL_DEF as VAULT_WRITE_DEF
from .vault_write import vault_write
from .web_search import TOOL_DEF as WEB_SEARCH_DEF
from .web_search import web_search
from .obsidian_cli import (
    READ_TOOL_DEF as OBSIDIAN_READ_DEF,
    CREATE_TOOL_DEF as OBSIDIAN_CREATE_DEF,
    MOVE_TOOL_DEF as OBSIDIAN_MOVE_DEF,
    LIST_TOOL_DEF as OBSIDIAN_LIST_DEF,
    obsidian_read,
    obsidian_create,
    obsidian_move,
    obsidian_list,
)
from .summarize_cli import TOOL_DEF as SUMMARIZE_DEF
from .summarize_cli import summarize_url
from .blogwatcher_cli import (
    SCAN_TOOL_DEF as BLOG_SCAN_DEF,
    ADD_TOOL_DEF as BLOG_ADD_DEF,
    LIST_TOOL_DEF as BLOG_LIST_DEF,
    ARTICLES_TOOL_DEF as BLOG_ARTICLES_DEF,
    READ_TOOL_DEF as BLOG_READ_DEF,
    blog_scan,
    blog_add,
    blog_list,
    blog_articles,
    blog_mark_read,
)

if TYPE_CHECKING:
    from src.engine.orchestrator import Orchestrator


def setup_tools() -> ToolRegistry:
    """Create and return a ToolRegistry with all standard tools registered.

    These are the tools available to sub-agents (search, read, write, fetch).
    Does NOT include route_to_agent (that's Chief-only).
    """
    registry = ToolRegistry()

    registry.register(
        name=PAPER_FETCH_DEF["name"],
        description=PAPER_FETCH_DEF["description"],
        input_schema=PAPER_FETCH_DEF["input_schema"],
        handler=paper_fetch,
    )

    registry.register(
        name=VAULT_WRITE_DEF["name"],
        description=VAULT_WRITE_DEF["description"],
        input_schema=VAULT_WRITE_DEF["input_schema"],
        handler=vault_write,
    )

    registry.register(
        name=VAULT_READ_DEF["name"],
        description=VAULT_READ_DEF["description"],
        input_schema=VAULT_READ_DEF["input_schema"],
        handler=vault_read,
    )

    registry.register(
        name=QMD_SEARCH_DEF["name"],
        description=QMD_SEARCH_DEF["description"],
        input_schema=QMD_SEARCH_DEF["input_schema"],
        handler=qmd_search,
    )

    registry.register(
        name=TERM_FEEDBACK_DEF["name"],
        description=TERM_FEEDBACK_DEF["description"],
        input_schema=TERM_FEEDBACK_DEF["input_schema"],
        handler=term_feedback,
    )

    registry.register(
        name=WEB_SEARCH_DEF["name"],
        description=WEB_SEARCH_DEF["description"],
        input_schema=WEB_SEARCH_DEF["input_schema"],
        handler=web_search,
    )

    registry.register(
        name=RSS_FETCH_DEF["name"],
        description=RSS_FETCH_DEF["description"],
        input_schema=RSS_FETCH_DEF["input_schema"],
        handler=rss_fetch,
    )

    # Obsidian CLI tools (vault operations with wiki-link awareness)
    # Note: search is handled by qmd_search (semantic), not obsidian-cli (keyword)
    registry.register(
        name=OBSIDIAN_READ_DEF["name"],
        description=OBSIDIAN_READ_DEF["description"],
        input_schema=OBSIDIAN_READ_DEF["input_schema"],
        handler=obsidian_read,
    )
    registry.register(
        name=OBSIDIAN_CREATE_DEF["name"],
        description=OBSIDIAN_CREATE_DEF["description"],
        input_schema=OBSIDIAN_CREATE_DEF["input_schema"],
        handler=obsidian_create,
    )
    registry.register(
        name=OBSIDIAN_MOVE_DEF["name"],
        description=OBSIDIAN_MOVE_DEF["description"],
        input_schema=OBSIDIAN_MOVE_DEF["input_schema"],
        handler=obsidian_move,
    )
    registry.register(
        name=OBSIDIAN_LIST_DEF["name"],
        description=OBSIDIAN_LIST_DEF["description"],
        input_schema=OBSIDIAN_LIST_DEF["input_schema"],
        handler=obsidian_list,
    )

    # Summarize CLI (URL/YouTube/PDF summarization)
    registry.register(
        name=SUMMARIZE_DEF["name"],
        description=SUMMARIZE_DEF["description"],
        input_schema=SUMMARIZE_DEF["input_schema"],
        handler=summarize_url,
    )

    # Blogwatcher CLI (persistent blog tracking with read/unread state)
    registry.register(
        name=BLOG_SCAN_DEF["name"],
        description=BLOG_SCAN_DEF["description"],
        input_schema=BLOG_SCAN_DEF["input_schema"],
        handler=blog_scan,
    )
    registry.register(
        name=BLOG_ADD_DEF["name"],
        description=BLOG_ADD_DEF["description"],
        input_schema=BLOG_ADD_DEF["input_schema"],
        handler=blog_add,
    )
    registry.register(
        name=BLOG_LIST_DEF["name"],
        description=BLOG_LIST_DEF["description"],
        input_schema=BLOG_LIST_DEF["input_schema"],
        handler=blog_list,
    )
    registry.register(
        name=BLOG_ARTICLES_DEF["name"],
        description=BLOG_ARTICLES_DEF["description"],
        input_schema=BLOG_ARTICLES_DEF["input_schema"],
        handler=blog_articles,
    )
    registry.register(
        name=BLOG_READ_DEF["name"],
        description=BLOG_READ_DEF["description"],
        input_schema=BLOG_READ_DEF["input_schema"],
        handler=blog_mark_read,
    )

    return registry


def setup_chief_tools(orchestrator: Orchestrator) -> ToolRegistry:
    """Create a ToolRegistry for the Chief Agent.

    The Chief gets route_to_agent (to delegate) but NOT the sub-agent tools
    (no direct vault/search access — it delegates instead).
    """
    registry = ToolRegistry()

    handler = create_route_handler(orchestrator)
    registry.register(
        name=ROUTE_DEF["name"],
        description=ROUTE_DEF["description"],
        input_schema=ROUTE_DEF["input_schema"],
        handler=handler,
    )

    return registry
