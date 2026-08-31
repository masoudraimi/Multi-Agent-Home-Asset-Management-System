"""Asset specialist LangGraph subgraph.

Uses the shared builder in `agents/_specialist.py` for the standard
enter → guardrail_in → retrieve → llm ↔ tools → guardrail_tool_output →
guardrail_out → exit shape, plus the asset-specific `handle_approval` node
that intercepts destructive `delete_asset` calls via LangGraph's `interrupt()`.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

import tools.db as db
from agents._specialist import SpecialistGraph
from agents.state import AgentState
from core.audit import audit
from core.logging import get_logger
from tools.langchain_tools import TOOLS

log = get_logger(__name__)


def handle_approval_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Human-in-the-loop approval gate for destructive actions.

    Reached only after `review_delete_asset` returned `approval_requested`.
    Pauses the graph via `interrupt(payload)`. When resumed with
    `Command(resume={"approved": bool})`, executes `db.delete_asset`
    directly (no additional LLM tokens spent) or reports the cancellation.
    """
    last_tm = _last_tool_message(state.get("messages", []))
    payload = _extract_approval_payload(last_tm)
    if not payload:
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
                request_id=request_id, actor="user", user_id=user_id, agent="asset",
                payload={"asset_id": asset_id, "result": result, "cascade_count": cascade_count},
            )
            audit(
                "approval_confirmed",
                request_id=request_id, actor="user", user_id=user_id, agent="asset",
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
                request_id=request_id, actor="user", user_id=user_id, agent="asset",
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
        request_id=request_id, actor="user", user_id=user_id, agent="asset",
        payload={"action": "delete_asset", "asset_id": asset_id},
    )
    log.info("approval_cancelled", request_id=request_id, asset_id=asset_id)
    return {
        "messages": [AIMessage(content=f"OK — I've cancelled the deletion of **{asset_name}**. No changes were made.")],
        "approval_result": "cancelled",
        "pending_approval": None,
    }


def _route_after_tools_asset(state: AgentState) -> str:
    """Send review_delete_asset results to handle_approval; everything else back to LLM."""
    last_tm = _last_tool_message(state.get("messages", []))
    if _extract_approval_payload(last_tm) is not None:
        return "handle_approval"
    return "llm"


def _last_tool_message(messages: list[BaseMessage]) -> ToolMessage | None:
    for m in reversed(messages):
        if isinstance(m, ToolMessage):
            return m
    return None


def _extract_approval_payload(tm: ToolMessage | None) -> dict[str, Any] | None:
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


def build_graph(checkpointer: Any = None) -> Any:
    """Compile the asset subgraph with the approval branch wired in."""
    spec = SpecialistGraph(agent_name="asset", tools=TOOLS)
    spec.set_approval_handler(handle_approval_node, _route_after_tools_asset)
    return spec.build(checkpointer=checkpointer)


# Module-level singleton — compile once, invoke many times.
GRAPH = build_graph()
