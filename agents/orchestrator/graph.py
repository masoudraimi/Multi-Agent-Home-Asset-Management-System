"""Orchestrator as a LangGraph — PHASE 4 SCAFFOLD (not yet wired).

Compiles cleanly but interrupt propagation from nested specialist subgraphs
is not implemented yet. Currently the app still routes through
`OrchestratorAgent._dispatch_async` (unchanged from Phase 3). This file
gives Phase 4 a starting point.

Intended topology:

    START -> classify -> Send() per route -> [asset | maintenance | insights] subgraph
                                         -> merge_responses
                                         -> END

For single-route queries the Send() fans out to one specialist and
`merge_responses` acts as a passthrough. Compound queries run specialists in
parallel and concatenate their outputs with per-agent headers, matching the
legacy behaviour in `OrchestratorAgent._merge_responses`.

Classification is Haiku via `agents.orchestrator.workflows.routing`; kept
deterministic (not a tool-calling supervisor) so classifier cost stays flat.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Send

from agents.orchestrator.workflows.routing import classify_intent
from agents.state import RouteName
from core.checkpointer import get_checkpointer
from core.logging import get_logger

log = get_logger(__name__)


class OrchestratorState(TypedDict, total=False):
    """State for the orchestrator supervisor graph.

    Distinct from `AgentState` (used by specialists). Specialist replies are
    merged in `specialist_outputs`, a dict keyed by agent name.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    request_id: str
    route: list[RouteName]
    specialist_outputs: Annotated[dict[str, str], operator.or_]
    specialist_metrics: Annotated[list[dict], operator.add]
    tokens_total: int
    tool_calls_total: int


# ── Nodes ────────────────────────────────────────────────────────────

def classify_node(state: OrchestratorState, config: RunnableConfig) -> dict[str, Any]:
    """Route the last user message to one or more specialists."""
    messages = state.get("messages", [])
    last_user = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    text = last_user.content if last_user and isinstance(last_user.content, str) else ""
    route = classify_intent(text) or ["asset"]
    log.info("orchestrator_classify", route=route, request_id=state.get("request_id"))
    return {"route": route}


async def run_specialist_node(state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
    """Invoke one specialist subgraph.

    Receives a per-agent payload built by the Send() dispatcher below.
    Emits `specialist_outputs[<agent>]` = final assistant text and
    `specialist_metrics` = one entry with usage / cost.
    """
    from agent.langgraph_adapter import run_graph_turn

    agent_name: str = state["agent_name"]
    user_message: str = state["user_message"]
    thread_id: str | None = state.get("thread_id")
    context = state["context"]

    if agent_name == "asset":
        from agents.asset.graph import GRAPH as SPECIALIST
    elif agent_name == "maintenance":
        from agents.maintenance.graph import GRAPH as SPECIALIST
    elif agent_name == "insights":
        from agents.insights.graph import GRAPH as SPECIALIST
    else:
        return {"specialist_outputs": {agent_name: ""}, "specialist_metrics": []}

    events = await run_graph_turn(
        SPECIALIST,
        user_message,
        context,
        agent_name=agent_name,
        thread_id=thread_id,
    )
    text = next((e["content"] for e in events if e.get("type") == "assistant_text"), "")
    metrics = next((e for e in events if e.get("type") == "metrics"), {})
    return {
        "specialist_outputs": {agent_name: text},
        "specialist_metrics": [{"agent": agent_name, "text": text, "events": events, "metrics": metrics}],
    }


def merge_node(state: OrchestratorState, config: RunnableConfig) -> dict[str, Any]:
    """Combine specialist outputs into one AIMessage."""
    route = state.get("route") or []
    outputs = state.get("specialist_outputs") or {}
    entries = state.get("specialist_metrics") or []

    if len(route) == 1:
        # Passthrough — the single specialist's text is the final answer.
        merged_text = outputs.get(route[0], "") or "I was unable to gather the information."
    else:
        parts: list[str] = []
        for agent in route:
            text = outputs.get(agent, "")
            if text:
                parts.append(f"**{agent.capitalize()}:**\n{text}")
        merged_text = "\n\n".join(parts) if parts else "I was unable to gather the information."

    total_tokens = 0
    total_tools = 0
    max_latency = 0
    for entry in entries:
        m = entry.get("metrics") or {}
        total_tokens += int(m.get("tokens", 0))
        total_tools += int(m.get("tool_call_count", 0))
        max_latency = max(max_latency, int(m.get("latency_ms", 0)))
    log.info(
        "orchestrator_merge",
        route=route,
        tokens_total=total_tokens,
        tools_total=total_tools,
        latency_ms=max_latency,
    )

    return {
        "messages": [AIMessage(content=merged_text, additional_kwargs={"agents_used": list(route)})],
        "tokens_total": total_tokens,
        "tool_calls_total": total_tools,
    }


# ── Dispatch ─────────────────────────────────────────────────────────

def dispatch_after_classify(state: OrchestratorState) -> list[Send]:
    """Fan out one Send() per selected route."""
    route = state.get("route") or ["asset"]
    user_message = _last_user_message(state.get("messages", []))
    metadata = {
        "user_message": user_message,
        "thread_id": _thread_id_from_state(state),
        "context": state.get("__context"),
    }
    return [
        Send(
            "run_specialist",
            {**metadata, "agent_name": agent},
        )
        for agent in route
    ]


def _last_user_message(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content if isinstance(m.content, str) else ""
    return ""


def _thread_id_from_state(state: OrchestratorState) -> str | None:
    # Consumers set thread_id in the RunnableConfig's configurable, not state.
    # This helper exists so tests can override without going through config.
    return None


# ── Assembler ────────────────────────────────────────────────────────

def build_graph(checkpointer: Any = None) -> Any:
    if checkpointer is None:
        checkpointer = get_checkpointer()

    graph = StateGraph(OrchestratorState)
    graph.add_node("classify", classify_node)
    graph.add_node("run_specialist", run_specialist_node)
    graph.add_node("merge", merge_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", dispatch_after_classify, ["run_specialist"])
    graph.add_edge("run_specialist", "merge")
    graph.add_edge("merge", END)

    return graph.compile(checkpointer=checkpointer)


# Phase 4 will wire GRAPH into the runner once interrupt propagation from
# nested specialist subgraphs is implemented. Until then callers must invoke
# `build_graph()` explicitly to opt in.
