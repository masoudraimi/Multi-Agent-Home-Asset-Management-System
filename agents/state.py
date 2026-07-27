"""Shared state schema for all LangGraph specialists and the orchestrator.

Every specialist subgraph (asset, maintenance, insights) and the orchestrator
graph share this TypedDict. The `messages` reducer merges tool call/results
across nodes; `asset_index` accumulates across turns within the checkpointer's
thread.

Fields marked "turn-scoped" (retrieved_context, iteration, tokens_*, usd_cost,
termination_reason, pending_approval, approval_result) are cleared at graph
entry — do NOT persist them across checkpoints.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

RouteName = Literal["asset", "maintenance", "insights"]
TerminationReason = Literal["ok", "budget", "max_iter", "guardrail", "error"]


class AgentState(TypedDict, total=False):
    # ── Conversation (persistent) ──────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Routing / control ──────────────────────────────────────────────
    route: list[RouteName]
    active_specialist: RouteName | None

    # ── Working memory (persistent, capped) ───────────────────────────
    # Asset name (lowercased) -> id. Refreshed after every tool call that
    # returns asset objects. Capped at 8 entries in the update helper.
    asset_index: dict[str, int]

    # ── Turn-scoped fields (reset at graph entry) ─────────────────────
    retrieved_context: list[dict[str, Any]]     # {"content", "score", "source"}
    iteration: int
    tokens_in: int
    tokens_out: int
    usd_cost: float
    termination_reason: TerminationReason | None

    # ── Session ────────────────────────────────────────────────────────
    user_id: str
    request_id: str                             # UUIDv7 assigned in rxapp/state.py

    # ── Human-in-the-loop (Phase 2 activates these) ───────────────────
    pending_approval: dict[str, Any] | None
    approval_result: Literal["confirmed", "cancelled"] | None


def make_initial_state(
    *,
    user_message: str,
    user_id: str,
    request_id: str,
    prior_messages: list[BaseMessage] | None = None,
    asset_index: dict[str, int] | None = None,
) -> AgentState:
    """Build a fresh state at the top of a turn, zeroing all turn-scoped fields."""
    from langchain_core.messages import HumanMessage

    prior = prior_messages or []
    return AgentState(
        messages=[*prior, HumanMessage(content=user_message)],
        route=[],
        active_specialist=None,
        asset_index=asset_index or {},
        retrieved_context=[],
        iteration=0,
        tokens_in=0,
        tokens_out=0,
        usd_cost=0.0,
        termination_reason=None,
        user_id=user_id,
        request_id=request_id,
        pending_approval=None,
        approval_result=None,
    )
