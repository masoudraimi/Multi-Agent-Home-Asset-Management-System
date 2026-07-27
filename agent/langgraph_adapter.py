"""Bridge between LangGraph specialist subgraphs and the current UI event
dict format consumed by `rxapp/state.py::send_message`.

Public API:
    await run_graph_turn(graph, user_message, context, agent_name) -> list[dict]

The list of returned events mirrors what `run_turn_in_loop` yields today,
so the Reflex handler consumes both interchangeably during the phased
migration.

Event shapes emitted (same as agent/runner.py):
    {"type": "routing", "agents": [name]}
    {"type": "tool_call", "name": <tool>, "args": {...}, "call_id": <id>}
    {"type": "tool_result", "name": <tool>, "call_id": <id>, "result": ...}
    {"type": "assistant_text", "content": <text>}
    {"type": "metrics", "latency_ms": int, "tokens": int, "tool_call_count": int, "agent": name}
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from agents.state import AgentState, make_initial_state
from core.logging import bind_correlation, get_logger
from core.memory.short_term import ConversationContext
from core.session import get_current_user_id_or_none

log = get_logger(__name__)


async def run_graph_turn(
    graph: Any,
    user_message: str,
    context: ConversationContext,
    *,
    agent_name: str,
    request_id: str | None = None,
    thread_id: str | None = None,
) -> list[dict]:
    """Invoke a LangGraph specialist and return UI events in the legacy shape.

    Bridges `ConversationContext` (prior turns + asset index) into the graph's
    `state["messages"]` on entry, and updates the context on exit so the
    next Reflex event handler pick up sees the new turn.
    """
    request_id = request_id or _new_request_id()
    user_id = get_current_user_id_or_none() or ""
    bind_correlation(request_id=request_id, user_id=user_id, agent=agent_name)

    prior_messages = _context_to_messages(context)
    initial: AgentState = make_initial_state(
        user_message=user_message,
        user_id=user_id,
        request_id=request_id,
        prior_messages=prior_messages,
        asset_index=dict(context._asset_ids),
    )

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id or f"{user_id}:{request_id}"},
        "metadata": {
            "request_id": request_id,
            "user_id": user_id,
            "agent": agent_name,
        },
        "tags": [agent_name, "phase1"],
        "recursion_limit": 50,
    }

    # Note: the caller (OrchestratorAgent) owns the "routing" event; adapter
    # emits only tool_call, tool_result, assistant_text, metrics, and (on
    # interrupt) pending_approval.
    events: list[dict] = []
    t0 = time.monotonic()
    try:
        final_state: AgentState = await graph.ainvoke(initial, config)
    except Exception:
        log.exception("graph_ainvoke_failed", agent=agent_name)
        events.append({
            "type": "assistant_text",
            "content": "Sorry — I hit an internal error. Please try again.",
        })
        events.append(_metrics_event(agent_name, tokens=0, tool_calls=0, latency_ms=_ms_since(t0)))
        return events

    events.extend(_messages_to_ui_events(initial.get("messages", []), final_state.get("messages", [])))

    interrupt_event = await _maybe_interrupt_event(graph, config, agent_name)
    if interrupt_event is not None:
        # Graph paused mid-turn; no final answer yet. Emit the pending
        # approval and the (partial) metrics so the UI knows what happened.
        events.append(interrupt_event)
        events.append(_metrics_event(
            agent_name,
            tokens=int(final_state.get("tokens_in", 0)) + int(final_state.get("tokens_out", 0)),
            tool_calls=_count_tool_calls(final_state.get("messages", [])),
            latency_ms=_ms_since(t0),
        ))
        log.info(
            "adapter_turn_interrupted",
            agent=agent_name,
            thread_id=config["configurable"]["thread_id"],
        )
        return events

    final_text = _last_assistant_text(final_state.get("messages", []))
    if final_text:
        events.append({"type": "assistant_text", "content": final_text})
        context.add_turn(user_message, final_text)

    for name, asset_id in (final_state.get("asset_index") or {}).items():
        context.track_asset(name, int(asset_id))

    events.append(_metrics_event(
        agent_name,
        tokens=int(final_state.get("tokens_in", 0)) + int(final_state.get("tokens_out", 0)),
        tool_calls=_count_tool_calls(final_state.get("messages", [])),
        latency_ms=_ms_since(t0),
    ))
    log.info(
        "adapter_turn_completed",
        agent=agent_name,
        tokens_in=final_state.get("tokens_in", 0),
        tokens_out=final_state.get("tokens_out", 0),
        usd_cost=round(float(final_state.get("usd_cost", 0.0)), 6),
        outcome=final_state.get("termination_reason") or "ok",
    )
    return events


async def resume_graph_turn(
    graph: Any,
    *,
    thread_id: str,
    approved: bool,
    context: ConversationContext,
    agent_name: str = "asset",
) -> list[dict]:
    """Resume a graph paused at an `interrupt()` call.

    Called by Reflex when the user clicks Confirm or Cancel on an approval
    card. Returns the same UI event dict list as `run_graph_turn`, minus the
    initial tool_call/tool_result events (those were already emitted during
    the pause turn).
    """
    request_id = _new_request_id()
    user_id = get_current_user_id_or_none() or ""
    bind_correlation(request_id=request_id, user_id=user_id, agent=agent_name)

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "metadata": {
            "request_id": request_id,
            "user_id": user_id,
            "agent": agent_name,
            "resume": True,
        },
        "tags": [agent_name, "phase2", "resume"],
        "recursion_limit": 50,
    }

    events: list[dict] = []
    t0 = time.monotonic()
    # Snapshot state before resume so we can diff new messages.
    pre_state = await graph.aget_state(config)
    pre_messages = list(pre_state.values.get("messages", []))

    try:
        final_state: AgentState = await graph.ainvoke(Command(resume={"approved": approved}), config)
    except Exception:
        log.exception("graph_resume_failed", agent=agent_name, thread_id=thread_id)
        events.append({
            "type": "assistant_text",
            "content": "Sorry — I hit an internal error while completing that action.",
        })
        events.append(_metrics_event(agent_name, tokens=0, tool_calls=0, latency_ms=_ms_since(t0)))
        return events

    events.extend(_messages_to_ui_events(pre_messages, final_state.get("messages", [])))

    final_text = _last_assistant_text(final_state.get("messages", []))
    if final_text:
        events.append({"type": "assistant_text", "content": final_text})
        context.add_turn(f"[approval:{'confirmed' if approved else 'cancelled'}]", final_text)

    for name, asset_id in (final_state.get("asset_index") or {}).items():
        context.track_asset(name, int(asset_id))

    events.append(_metrics_event(
        agent_name,
        tokens=int(final_state.get("tokens_in", 0)) + int(final_state.get("tokens_out", 0)),
        tool_calls=_count_tool_calls(final_state.get("messages", [])),
        latency_ms=_ms_since(t0),
    ))
    log.info(
        "adapter_resume_completed",
        agent=agent_name,
        thread_id=thread_id,
        approved=approved,
        outcome=final_state.get("termination_reason") or "ok",
    )
    return events


async def _maybe_interrupt_event(graph: Any, config: RunnableConfig, agent_name: str) -> dict | None:
    """If the graph is paused at an interrupt, return a pending_approval UI event."""
    state = await graph.aget_state(config)
    if not state.tasks:
        return None
    for task in state.tasks:
        for iv in getattr(task, "interrupts", ()) or ():
            payload = iv.value if isinstance(iv.value, dict) else {"raw": str(iv.value)}
            inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
            request_id = payload.get("request_id") or config["metadata"].get("request_id", "")
            asset_name = inner.get("asset_name", "unknown")
            asset_id = inner.get("asset_id", "?")
            cascade = inner.get("maintenance_records_to_delete", 0)
            action = payload.get("action", "unknown_action")
            return {
                "type": "pending_approval",
                "request_id": request_id,
                "agent_name": agent_name,
                "action_description": (
                    f"Delete asset: {asset_name} (id={asset_id})."
                    f" This will also remove {cascade} maintenance record(s)."
                ),
                "payload_str": json.dumps(inner, indent=2),
                "action": action,
                "thread_id": config["configurable"]["thread_id"],
            }
    return None


# ── Helpers ──────────────────────────────────────────────────────────────

def _new_request_id() -> str:
    return "req_" + uuid.uuid4().hex[:16]


def _ms_since(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


def _context_to_messages(context: ConversationContext) -> list[BaseMessage]:
    """Convert the last 5 (user, assistant) turns to alternating messages."""
    out: list[BaseMessage] = []
    for user, assistant in context._turns[-5:]:
        if user:
            out.append(HumanMessage(content=user))
        if assistant:
            out.append(AIMessage(content=assistant))
    return out


def _messages_to_ui_events(initial: list[BaseMessage], final: list[BaseMessage]) -> list[dict]:
    """Extract tool_call / tool_result events from messages new in this turn."""
    seen_ids = {id(m) for m in initial}
    new_messages = [m for m in final if id(m) not in seen_ids]

    events: list[dict] = []
    tool_call_names: dict[str, str] = {}       # call_id -> tool name
    for m in new_messages:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls or []:
                call_id = tc.get("id", "")
                name = tc.get("name", "")
                args = tc.get("args", {}) or {}
                tool_call_names[call_id] = name
                events.append({
                    "type": "tool_call",
                    "name": name,
                    "args": args,
                    "call_id": call_id,
                })
        elif isinstance(m, ToolMessage):
            call_id = getattr(m, "tool_call_id", "") or ""
            name = tool_call_names.get(call_id) or getattr(m, "name", "") or ""
            content = m.content
            if isinstance(content, (dict, list)):
                content = json.dumps(content)
            events.append({
                "type": "tool_result",
                "name": name,
                "call_id": call_id,
                "result": content,
            })
    return events


def _last_assistant_text(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip():
            return m.content
        if isinstance(m, AIMessage) and isinstance(m.content, list):
            parts = [p.get("text", "") for p in m.content if isinstance(p, dict) and p.get("type") == "text"]
            joined = "".join(parts).strip()
            if joined:
                return joined
    return ""


def _count_tool_calls(messages: list[BaseMessage]) -> int:
    return sum(1 for m in messages if isinstance(m, ToolMessage))


def _metrics_event(agent: str, *, tokens: int, tool_calls: int, latency_ms: int) -> dict:
    return {
        "type": "metrics",
        "latency_ms": latency_ms,
        "tokens": tokens,
        "tool_call_count": tool_calls,
        "agent": agent,
    }
