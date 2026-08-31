"""Deep-agent-powered multi-step research tool for the insights specialist.

Demonstrates real usage of LangChain's Deep Agents library
(github.com/langchain-ai/deepagents, built on LangGraph) for genuinely
exploratory, multi-step analysis — e.g. "why is my utility bill high",
spanning maintenance history + asset data + checklist compliance — where a
single tool-calling loop under-explores.

Compatibility spike result (why this is a tool, not a wholesale graph swap):
`create_deep_agent` compiles cleanly against our existing @tool wrappers and
`BaseChatModel` instances, and its `DeepAgentState` is a TypedDict that can
be subclassed with extra fields without breaking compilation — the state
shape is genuinely compatible. But its own graph topology (`model <-> tools`
plus its built-in planning/filesystem middleware) has none of the
governance nodes `agents/_specialist.py::SpecialistGraph` builds — rate
limiting, layered injection defense, RAG auto-retrieve, audit logging.
Reimplementing those as deepagents middleware is a materially larger,
separate effort. So the deep agent runs *behind* the existing security
perimeter as a tool call: `guardrail_in` already scanned the user's message
before this can be reached, and `guardrail_tool_output` scans this tool's
result like any other before it reaches the LLM or the user. Its internal
token/LLM cost isn't tracked in the turn's `usd_cost` — a documented
limitation, consistent with the injection classifier's cost also being
untracked there.
"""

from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from core.llm import build_chat_model
from core.logging import get_logger
from core.metrics import emit_tool_call
from tools.langchain_tools import TOOLS_BY_NAME

log = get_logger(__name__)

# Read-only subset — a research sub-agent should investigate, not mutate.
_RESEARCH_TOOL_NAMES = (
    "list_assets", "search_assets", "get_asset_history",
    "get_upcoming_maintenance", "get_expiring_warranties", "recall_knowledge",
)

_SYSTEM_PROMPT = (
    "You are a research sub-agent for a home-asset-management assistant. "
    "Given an open-ended analysis question, plan and execute the read-only "
    "lookups needed to answer it thoroughly, then write a clear, concise "
    "final answer. You only have read-only tools — you cannot modify data."
)

_deep_agent: Any = None


def _get_deep_agent() -> Any:
    """Built once, lazily — avoids constructing a chat model (which needs
    real credentials) at import time, so importing this module stays safe
    for tests that never actually call the tool."""
    global _deep_agent
    if _deep_agent is None:
        research_tools = [TOOLS_BY_NAME[name] for name in _RESEARCH_TOOL_NAMES]
        model = build_chat_model(tier="sonnet", temperature=0.0, max_tokens=4096)
        _deep_agent = create_deep_agent(model=model, tools=research_tools, system_prompt=_SYSTEM_PROMPT)
    return _deep_agent


@tool("deep_research_analysis")
def deep_research_analysis(query: str) -> dict:
    """Run a multi-step, planned research pass over the home-asset data to
    answer an open-ended analysis question (e.g. "why is my utility bill
    high", "give me a full picture of my HVAC system's condition").

    Use this instead of chaining several lookups yourself when the question
    genuinely spans multiple data sources and needs its own investigation
    plan. Not for simple single-lookup questions — those are cheaper and
    faster answered directly.

    query: the open-ended research question to investigate.
    """
    log.info("deep_research_started", query=query[:200])
    try:
        agent = _get_deep_agent()
        result = agent.invoke({"messages": [HumanMessage(content=query)]})
    except Exception:
        emit_tool_call("deep_research_analysis", "error")
        log.exception("deep_research_failed")
        raise
    emit_tool_call("deep_research_analysis", "success")

    messages = result.get("messages", [])
    final_text = ""
    steps = 0
    for m in messages:
        if getattr(m, "tool_calls", None):
            steps += len(m.tool_calls)
        if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip():
            final_text = m.content
    return {"analysis": final_text, "steps_taken": steps}
