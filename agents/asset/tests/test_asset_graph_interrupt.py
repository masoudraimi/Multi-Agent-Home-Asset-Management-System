"""Phase 2 tests: interrupt-based approval flow for delete_asset.

Exercises the full pause/resume cycle offline:
  1. LLM asks to delete an asset → calls review_delete_asset
  2. Graph interrupts at handle_approval
  3. Adapter emits pending_approval event
  4. Resume with approved=True → db.delete_asset runs → confirmation AIMessage
  5. Resume with approved=False → no delete → cancellation AIMessage

The stub `db.delete_asset` records whether it was called and with what asset_id,
so we can assert the direct-execution path without touching a real database.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from core.session import set_current_user


class _StubChatModel:
    def __init__(self, responses: list[AIMessage]) -> None:
        self._iter = iter(responses)

    def bind_tools(self, *_a: Any, **_kw: Any) -> "_StubChatModel":
        return self

    def invoke(self, _messages: Any, *_a: Any, **_kw: Any) -> AIMessage:
        return next(self._iter)


def _tool_call_delete_asset(asset_id: int, call_id: str = "call_1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "review_delete_asset",
            "args": {"asset_id": asset_id},
            "id": call_id,
            "type": "tool_call",
        }],
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
    )


def _install_llm(monkeypatch: pytest.MonkeyPatch, responses: list[AIMessage]) -> None:
    monkeypatch.setattr("agents._specialist.build_chat_model", lambda *a, **kw: _StubChatModel(responses))


def _install_delete_recorder(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace tools.db.delete_asset with a recorder that returns a fixed result."""
    calls: list[int] = []

    def _delete(asset_id: int) -> dict:
        calls.append(asset_id)
        return {"status": "deleted", "asset_id": asset_id, "name": "House Gutters"}

    monkeypatch.setattr("tools.db.delete_asset", _delete)
    # Also patch the reference inside graph.py (bound at import time)
    monkeypatch.setattr("agents.asset.graph.db.delete_asset", _delete)
    return {"calls": calls}


def _install_review_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """review_delete_asset returns an approval_requested payload without hitting the DB."""

    def _review(asset_id: int) -> dict:
        return {
            "status": "approval_requested",
            "asset_id": asset_id,
            "asset_name": "House Gutters",
            "maintenance_records_to_delete": 3,
        }

    monkeypatch.setattr("tools.db.review_delete_asset", _review)
    # Also for the workflows shim that langchain_tools might reach through
    monkeypatch.setattr("agents.asset.workflows.deletion.review_delete_asset", _review)


def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


@pytest.mark.asyncio
async def test_interrupt_then_approve_executes_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    set_current_user("test-user")
    _install_review_stub(monkeypatch)
    recorder = _install_delete_recorder(monkeypatch)
    # LLM's first turn asks to delete; no second turn required — handle_approval
    # produces the final AIMessage directly.
    _install_llm(monkeypatch, [_tool_call_delete_asset(4)])

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command
    from agents.asset.graph import build_graph
    from agents.state import make_initial_state

    graph = build_graph(checkpointer=InMemorySaver())
    thread_id = f"test:{uuid.uuid4().hex[:8]}"
    config = _thread_config(thread_id)

    initial = make_initial_state(
        user_message="delete house gutters id 4",
        user_id="test-user",
        request_id="req_delete_1",
    )
    result = await graph.ainvoke(initial, config)

    # Graph should be paused, no delete executed yet
    assert recorder["calls"] == []
    state = await graph.aget_state(config)
    assert state.tasks, "graph should have a pending interrupt task"
    interrupt_payload = state.tasks[0].interrupts[0].value
    assert interrupt_payload["action"] == "delete_asset"
    assert interrupt_payload["payload"]["asset_id"] == 4

    # Resume with approval
    resumed = await graph.ainvoke(Command(resume={"approved": True}), config)
    assert recorder["calls"] == [4]
    last_msg = resumed["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert "Done" in last_msg.content and "House Gutters" in last_msg.content
    assert resumed.get("approval_result") == "confirmed"
    assert resumed.get("pending_approval") is None


@pytest.mark.asyncio
async def test_interrupt_then_cancel_does_not_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    set_current_user("test-user")
    _install_review_stub(monkeypatch)
    recorder = _install_delete_recorder(monkeypatch)
    _install_llm(monkeypatch, [_tool_call_delete_asset(5)])

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command
    from agents.asset.graph import build_graph
    from agents.state import make_initial_state

    graph = build_graph(checkpointer=InMemorySaver())
    thread_id = f"test:{uuid.uuid4().hex[:8]}"
    config = _thread_config(thread_id)

    initial = make_initial_state(
        user_message="delete asset id 5",
        user_id="test-user",
        request_id="req_delete_2",
    )
    await graph.ainvoke(initial, config)
    # Cancel
    resumed = await graph.ainvoke(Command(resume={"approved": False}), config)

    assert recorder["calls"] == []      # never deleted
    last_msg = resumed["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert "cancelled" in last_msg.content.lower()
    assert resumed.get("approval_result") == "cancelled"


@pytest.mark.asyncio
async def test_adapter_emits_pending_approval_event(monkeypatch: pytest.MonkeyPatch) -> None:
    set_current_user("test-user")
    _install_review_stub(monkeypatch)
    _install_delete_recorder(monkeypatch)
    _install_llm(monkeypatch, [_tool_call_delete_asset(7)])

    from langgraph.checkpoint.memory import InMemorySaver
    from agents.asset.graph import build_graph
    from agent.langgraph_adapter import run_graph_turn
    from core.memory.short_term import ConversationContext

    graph = build_graph(checkpointer=InMemorySaver())
    ctx = ConversationContext()

    events = await run_graph_turn(
        graph, "delete id 7", ctx,
        agent_name="asset",
        request_id="req_adapter_delete",
        thread_id="test-adapter-thread",
    )

    types = [e["type"] for e in events]
    # tool_call and tool_result for review_delete_asset, then pending_approval, then metrics
    assert "tool_call" in types
    assert "tool_result" in types
    assert "pending_approval" in types
    assert "metrics" in types
    # No assistant_text yet — the graph is paused
    assert "assistant_text" not in types

    approval_event = next(e for e in events if e["type"] == "pending_approval")
    assert approval_event["agent_name"] == "asset"
    assert approval_event["action"] == "delete_asset"
    assert "House Gutters" in approval_event["action_description"]
    payload = json.loads(approval_event["payload_str"])
    assert payload["asset_id"] == 7
    # Thread ID is required for the caller to resume later
    assert approval_event["thread_id"] == "test-adapter-thread"


@pytest.mark.asyncio
async def test_resume_via_adapter_produces_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    set_current_user("test-user")
    _install_review_stub(monkeypatch)
    recorder = _install_delete_recorder(monkeypatch)
    _install_llm(monkeypatch, [_tool_call_delete_asset(9)])

    from langgraph.checkpoint.memory import InMemorySaver
    from agents.asset.graph import build_graph
    from agent.langgraph_adapter import run_graph_turn, resume_graph_turn
    from core.memory.short_term import ConversationContext

    graph = build_graph(checkpointer=InMemorySaver())
    ctx = ConversationContext()
    thread_id = f"test-thread-{uuid.uuid4().hex[:6]}"

    await run_graph_turn(
        graph, "delete id 9", ctx,
        agent_name="asset", request_id="req_r1", thread_id=thread_id,
    )
    assert recorder["calls"] == []          # not yet deleted

    events = await resume_graph_turn(graph, thread_id=thread_id, approved=True, context=ctx, agent_name="asset")
    assert recorder["calls"] == [9]

    text = next((e["content"] for e in events if e["type"] == "assistant_text"), "")
    assert "Done" in text and "House Gutters" in text
    metrics = next(e for e in events if e["type"] == "metrics")
    assert metrics["agent"] == "asset"
