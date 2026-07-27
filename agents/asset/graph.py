"""Asset specialist as a LangGraph subgraph.

Feature-flagged via `USE_LANGGRAPH=asset` (or `all`). When active, the
orchestrator routes asset intents through this graph instead of the legacy
BaseAgent path.

Shape:
    START -> enter -> guardrail_in -> llm <-> tools -> guardrail_out -> exit -> END

Phase 1 keeps the existing string-sentinel approval flow (`__approval_confirmed__`
in message history triggers the delete). Phase 2 replaces that with an
explicit `interrupt()` node.

Building block used by other specialists in Phase 3 — see `agents/state.py`
for the shared TypedDict.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

import tools.db as db
from agents.state import AgentState
from core.audit import audit
from core.checkpointer import get_checkpointer
from core.guardrails import Guardrails
from core.llm import build_chat_model
from core.logging import bind_correlation, clear_correlation, get_logger
from core.metrics import (
    TurnSummary,
    emit_budget_breach,
    emit_guardrail_block,
    record_turn,
)
from core.models import get_provider, resolve_model
from core.pricing import estimate_cost_usd, is_priced
from core.registry import AgentRegistry
from core.session import set_current_user
from tools.langchain_tools import TOOLS

log = get_logger(__name__)

_CONFIG = AgentRegistry().get("asset")
_GUARDRAILS = Guardrails(_CONFIG.guardrails)
_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


def _load_system_prompt() -> str:
    raw = _PROMPT_PATH.read_text(encoding="utf-8")
    return raw.replace("{today}", date.today().isoformat())


_SYSTEM_PROMPT = _load_system_prompt()


# Sentinel messages the app sends when the user confirms/cancels an approval
# card. They're kept out of the injection guard (they're internal control
# strings, not user input) — see guardrail_in_node.
_INTERNAL_SENTINELS = frozenset({"__approval_confirmed__", "__approval_cancelled__"})


# ── Nodes ────────────────────────────────────────────────────────────────

def enter_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Bind correlation IDs, apply user context, and reset turn-scoped fields."""
    metadata = config.get("metadata", {}) or {}
    bind_correlation(
        request_id=state.get("request_id") or metadata.get("request_id"),
        user_id=state.get("user_id") or metadata.get("user_id"),
        agent="asset",
    )
    if user_id := state.get("user_id"):
        set_current_user(user_id)
    log.info("graph_enter", agent="asset", messages=len(state.get("messages", [])))
    # Reset turn-scoped counters here (they may have leaked from a prior invocation)
    return {
        "active_specialist": "asset",
        "iteration": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "usd_cost": 0.0,
        "termination_reason": None,
        "retrieved_context": [],
    }


def guardrail_in_node(state: AgentState) -> dict[str, Any]:
    """Prompt-injection check on the last human message."""
    messages = state.get("messages", [])
    last_user = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)),
        None,
    )
    if last_user is None:
        return {}
    text = last_user.content if isinstance(last_user.content, str) else ""
    if text in _INTERNAL_SENTINELS:
        return {}
    if _GUARDRAILS.is_injected(text):
        emit_guardrail_block("injection")
        log.warning("guardrail_injection_blocked", preview=text[:80])
        return {
            "messages": [AIMessage(content="I cannot process that request.")],
            "termination_reason": "guardrail",
        }
    return {}


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
)
def _invoke_llm(llm: Any, messages: list[BaseMessage]) -> AIMessage:
    """LLM call with tenacity-driven retry (3 attempts, 1-8s exp backoff)."""
    return llm.invoke(messages)


def llm_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Invoke the LLM. Handles budget/iteration limits + cost accounting."""
    iteration = int(state.get("iteration", 0)) + 1
    usd_so_far = float(state.get("usd_cost", 0.0))

    if iteration > _CONFIG.max_turns:
        log.warning("max_iter_reached", iteration=iteration, cap=_CONFIG.max_turns)
        emit_budget_breach("asset", "max_iter")
        return {
            "iteration": iteration,
            "termination_reason": "max_iter",
            "messages": [AIMessage(content="I've reached my step limit for this turn. Please try again with a narrower request.")],
        }
    if _CONFIG.budget_usd is not None and usd_so_far >= _CONFIG.budget_usd:
        log.warning("budget_reached", usd_so_far=usd_so_far, cap=_CONFIG.budget_usd)
        emit_budget_breach("asset", "usd")
        return {
            "iteration": iteration,
            "termination_reason": "budget",
            "messages": [AIMessage(content="I've reached the cost budget for this turn. Please try again.")],
        }

    llm = build_chat_model(tier="sonnet", temperature=0.0, max_tokens=4096, timeout_s=30.0).bind_tools(TOOLS)

    system_prompt = _SYSTEM_PROMPT
    if hint := _working_memory_hint(state.get("asset_index", {})):
        system_prompt = system_prompt + hint

    messages_in: list[BaseMessage] = [SystemMessage(content=system_prompt), *state.get("messages", [])]

    t0 = time.monotonic()
    resp: AIMessage = _invoke_llm(llm, messages_in)
    duration_ms = int((time.monotonic() - t0) * 1000)

    usage = getattr(resp, "usage_metadata", None) or {}
    in_tok = int(usage.get("input_tokens", 0))
    out_tok = int(usage.get("output_tokens", 0))
    model_name = resolve_model("sonnet")
    delta_usd = estimate_cost_usd(model_name, in_tok, out_tok)

    log.info(
        "llm_finished",
        iteration=iteration,
        duration_ms=duration_ms,
        tokens_in=in_tok,
        tokens_out=out_tok,
        delta_usd=round(delta_usd, 6),
        tool_calls=len(getattr(resp, "tool_calls", []) or []),
        priced=is_priced(model_name),
    )

    return {
        "messages": [resp],
        "iteration": iteration,
        "tokens_in": int(state.get("tokens_in", 0)) + in_tok,
        "tokens_out": int(state.get("tokens_out", 0)) + out_tok,
        "usd_cost": usd_so_far + delta_usd,
    }


# ToolNode from LangGraph handles ToolMessage plumbing; we wrap it to
# also extract asset IDs from results into asset_index.
_tool_node = ToolNode(TOOLS)


def tools_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Run pending tool calls, then extract asset IDs into asset_index."""
    result = _tool_node.invoke(state)
    tool_messages: list[ToolMessage] = result.get("messages", [])

    updated_index = dict(state.get("asset_index", {}))
    for tm in tool_messages:
        _absorb_asset_ids(tm, updated_index)

    return {
        "messages": tool_messages,
        "asset_index": _cap_index(updated_index),
    }


def handle_approval_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Human-in-the-loop approval gate for destructive actions.

    Reached only after `review_delete_asset` returned `approval_requested`.
    Pauses the graph via `interrupt(payload)`. When resumed with
    `Command(resume={"approved": bool})`, either executes `db.delete_asset`
    directly (no additional LLM tokens spent) or reports the cancellation.
    """
    last_tm = _last_tool_message(state.get("messages", []))
    payload = _extract_approval_payload(last_tm)
    if not payload:
        # Router misfired; fall through with no state mutation.
        return {}

    request_id = state.get("request_id", "")
    user_id = state.get("user_id", "")

    audit(
        "approval_requested",
        request_id=request_id,
        actor="agent",
        user_id=user_id,
        agent="asset",
        payload={
            "action": "delete_asset",
            "asset_id": payload.get("asset_id"),
            "asset_name": payload.get("asset_name"),
            "maintenance_records_to_delete": payload.get("maintenance_records_to_delete", 0),
        },
    )
    log.info("interrupt_awaiting_approval", request_id=request_id, asset_id=payload.get("asset_id"))

    # ── Graph pauses here. Resumes with {"approved": bool} via Command(resume=...) ──
    approval = interrupt({
        "action": "delete_asset",
        "request_id": request_id,
        "payload": payload,
    })

    approved = bool(approval.get("approved")) if isinstance(approval, dict) else False
    asset_id = int(payload.get("asset_id", 0))
    asset_name = str(payload.get("asset_name", ""))
    cascade_count = int(payload.get("maintenance_records_to_delete", 0))

    if approved:
        try:
            result = db.delete_asset(asset_id)
            audit(
                "asset_deleted",
                request_id=request_id,
                actor="user",
                user_id=user_id,
                agent="asset",
                payload={"asset_id": asset_id, "result": result, "cascade_count": cascade_count},
            )
            audit(
                "approval_confirmed",
                request_id=request_id,
                actor="user",
                user_id=user_id,
                agent="asset",
                payload={"action": "delete_asset", "asset_id": asset_id},
            )
            log.info("delete_executed", request_id=request_id, asset_id=asset_id)
            content = (
                f"Done — deleted **{asset_name}** (id={asset_id})."
                f" {cascade_count} maintenance record(s) were also removed."
            )
        except Exception as exc:
            log.exception("delete_failed_post_approval", request_id=request_id, asset_id=asset_id)
            audit(
                "asset_delete_failed",
                request_id=request_id,
                actor="user",
                user_id=user_id,
                agent="asset",
                payload={"asset_id": asset_id, "error": str(exc)[:500]},
            )
            content = (
                f"I hit an error while deleting **{asset_name}** (id={asset_id}): {exc}."
                " The record is still present — try again or check with an administrator."
            )
        return {
            "messages": [AIMessage(content=content)],
            "approval_result": "confirmed",
            "pending_approval": None,
        }

    audit(
        "approval_cancelled",
        request_id=request_id,
        actor="user",
        user_id=user_id,
        agent="asset",
        payload={"action": "delete_asset", "asset_id": asset_id},
    )
    log.info("approval_cancelled", request_id=request_id, asset_id=asset_id)
    return {
        "messages": [AIMessage(content=f"OK — I've cancelled the deletion of **{asset_name}**. No changes were made.")],
        "approval_result": "cancelled",
        "pending_approval": None,
    }


def guardrail_out_node(state: AgentState) -> dict[str, Any]:
    """Sanitize the final assistant message (PII + max length)."""
    messages = state.get("messages", [])
    last = messages[-1] if messages else None
    if not isinstance(last, AIMessage):
        return {}
    content = last.content if isinstance(last.content, str) else str(last.content)
    sanitized = _GUARDRAILS.sanitize_output(content)
    if sanitized == content:
        return {}
    return {"messages": [AIMessage(content=sanitized, id=last.id)]}


def exit_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Emit final metrics and clear correlation IDs."""
    outcome = state.get("termination_reason") or "ok"
    provider = get_provider().value
    record_turn(
        TurnSummary(
            ts=time.time(),
            request_id=state.get("request_id", ""),
            user_id=state.get("user_id", ""),
            agent="asset",
            provider=provider,
            outcome=outcome,
            duration_s=0.0,  # accurate wall-clock is measured by the adapter
            cost_usd=float(state.get("usd_cost", 0.0)),
            tool_calls=_count_tool_calls(state.get("messages", [])),
            tokens_in=int(state.get("tokens_in", 0)),
            tokens_out=int(state.get("tokens_out", 0)),
            termination_reason=state.get("termination_reason"),
        )
    )
    log.info(
        "graph_exit",
        outcome=outcome,
        usd_cost=round(float(state.get("usd_cost", 0.0)), 6),
        iteration=state.get("iteration", 0),
    )
    clear_correlation()
    return {}


# ── Edge conditions ──────────────────────────────────────────────────────

def _route_after_guardrail_in(state: AgentState) -> str:
    return "exit" if state.get("termination_reason") == "guardrail" else "llm"


def _route_after_llm(state: AgentState) -> str:
    """After the LLM: run tools if there are tool_calls, else exit via guardrail_out."""
    if state.get("termination_reason") in ("max_iter", "budget"):
        return "guardrail_out"
    messages = state.get("messages", [])
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return "guardrail_out"


def _route_after_tools(state: AgentState) -> str:
    """After tools: route to approval gate if delete was requested, else back to LLM."""
    last_tm = _last_tool_message(state.get("messages", []))
    if _extract_approval_payload(last_tm) is not None:
        return "handle_approval"
    return "llm"


# ── Helpers ──────────────────────────────────────────────────────────────

def _last_tool_message(messages: list[BaseMessage]) -> ToolMessage | None:
    for m in reversed(messages):
        if isinstance(m, ToolMessage):
            return m
    return None


def _extract_approval_payload(tm: ToolMessage | None) -> dict[str, Any] | None:
    """If `tm` is a review_delete_asset result requesting approval, return its payload."""
    if tm is None or tm.name != "review_delete_asset":
        return None
    content = tm.content
    try:
        data = json.loads(content) if isinstance(content, str) else content
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("status") != "approval_requested":
        return None
    return data


def _working_memory_hint(index: dict[str, int]) -> str:
    if not index:
        return ""
    items = ", ".join(f"{n} (id={i})" for n, i in list(index.items())[-8:])
    return f"\n\n[Assets referenced this session: {items}]"


def _absorb_asset_ids(tm: ToolMessage, index: dict[str, int]) -> None:
    """Extract (name, id) pairs from a tool result and stash in the index."""
    if tm.name not in ("list_assets", "search_assets", "get_asset_history", "add_asset"):
        return
    content = tm.content
    try:
        data = json.loads(content) if isinstance(content, str) else content
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(data, dict):
        return
    if tm.name in ("list_assets", "search_assets"):
        for asset in data.get("assets", []) or []:
            if isinstance(asset, dict):
                _put(index, asset.get("name", ""), asset.get("id", 0))
    elif tm.name == "get_asset_history":
        asset = data.get("asset") or {}
        if isinstance(asset, dict):
            _put(index, asset.get("name", ""), asset.get("id", 0))
    elif tm.name == "add_asset":
        if data.get("status") == "created":
            _put(index, data.get("name", ""), data.get("asset_id", 0))


def _put(index: dict[str, int], name: str, id_: Any) -> None:
    if isinstance(name, str) and name and isinstance(id_, int) and id_:
        index[name.lower()] = id_


def _cap_index(index: dict[str, int], limit: int = 8) -> dict[str, int]:
    if len(index) <= limit:
        return index
    return dict(list(index.items())[-limit:])


def _count_tool_calls(messages: list[BaseMessage]) -> int:
    return sum(1 for m in messages if isinstance(m, ToolMessage))


# ── Graph builder ────────────────────────────────────────────────────────

def build_graph(checkpointer: Any = None) -> Any:
    """Assemble and compile the asset subgraph.

    The default `checkpointer=None` means fetch the process-wide instance from
    `core.checkpointer.get_checkpointer()`. Tests can pass an explicit
    `InMemorySaver()` (or None to opt out) to isolate state.
    """
    if checkpointer is None:
        checkpointer = get_checkpointer()

    graph = StateGraph(AgentState)
    graph.add_node("enter", enter_node)
    graph.add_node("guardrail_in", guardrail_in_node)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", tools_node)
    graph.add_node("handle_approval", handle_approval_node)
    graph.add_node("guardrail_out", guardrail_out_node)
    graph.add_node("exit", exit_node)

    graph.add_edge(START, "enter")
    graph.add_edge("enter", "guardrail_in")
    graph.add_conditional_edges("guardrail_in", _route_after_guardrail_in, {"llm": "llm", "exit": "exit"})
    graph.add_conditional_edges(
        "llm",
        _route_after_llm,
        {"tools": "tools", "guardrail_out": "guardrail_out"},
    )
    graph.add_conditional_edges(
        "tools",
        _route_after_tools,
        {"llm": "llm", "handle_approval": "handle_approval"},
    )
    graph.add_edge("handle_approval", "guardrail_out")
    graph.add_edge("guardrail_out", "exit")
    graph.add_edge("exit", END)

    return graph.compile(checkpointer=checkpointer)


# Module-level singleton — compile once, invoke many times.
GRAPH = build_graph()
