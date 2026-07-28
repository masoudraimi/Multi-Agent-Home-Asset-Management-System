"""Structural smoke tests for the insights LangGraph subgraph."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage

from core.session import set_current_user


class _StubChatModel:
    def __init__(self, responses: list[AIMessage]) -> None:
        self._iter = iter(responses)

    def bind_tools(self, *_a: Any, **_kw: Any) -> "_StubChatModel":
        return self

    def invoke(self, _messages: Any, *_a: Any, **_kw: Any) -> AIMessage:
        return next(self._iter)


def _install_stub_llm(monkeypatch: pytest.MonkeyPatch, responses: list[AIMessage]) -> None:
    monkeypatch.setattr("agents._specialist.build_chat_model", lambda *a, **kw: _StubChatModel(responses))


def test_graph_compiles_without_approval_branch() -> None:
    from agents.insights.graph import GRAPH
    nodes = set(GRAPH.get_graph().nodes.keys())
    assert {"enter", "guardrail_in", "llm", "tools", "guardrail_out", "exit"} <= nodes
    assert "handle_approval" not in nodes


@pytest.mark.asyncio
async def test_direct_answer_no_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    set_current_user("test-user")
    _install_stub_llm(monkeypatch, [AIMessage(content="You spent $412 on HVAC this year.")])

    from langgraph.checkpoint.memory import InMemorySaver
    from agents.insights.graph import build_graph
    from agents.state import make_initial_state

    graph = build_graph(checkpointer=InMemorySaver())
    initial = make_initial_state(
        user_message="how much did I spend on HVAC?",
        user_id="test-user",
        request_id="req_i1",
    )
    final = await graph.ainvoke(initial, {"configurable": {"thread_id": "t-i1"}})
    assert isinstance(final["messages"][-1], AIMessage)
    assert "$412" in final["messages"][-1].content
