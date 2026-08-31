"""Structural smoke tests for the maintenance LangGraph subgraph."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage

from core.session import set_current_user


class _StubChatModel:
    def __init__(self, responses: list[AIMessage], *, captured_calls: list | None = None) -> None:
        self._iter = iter(responses)
        self._captured_calls = captured_calls

    def bind_tools(self, *_a: Any, **_kw: Any) -> "_StubChatModel":
        return self

    def invoke(self, messages: Any, *_a: Any, **_kw: Any) -> AIMessage:
        if self._captured_calls is not None:
            self._captured_calls.append(messages)
        return next(self._iter)


def _install_stub_llm(
    monkeypatch: pytest.MonkeyPatch, responses: list[AIMessage], *, captured_calls: list | None = None
) -> None:
    monkeypatch.setattr(
        "agents._specialist.build_chat_model",
        lambda *a, **kw: _StubChatModel(responses, captured_calls=captured_calls),
    )


def test_graph_compiles_without_approval_branch() -> None:
    from agents.maintenance.graph import GRAPH
    nodes = set(GRAPH.get_graph().nodes.keys())
    assert {"enter", "guardrail_in", "llm", "tools", "guardrail_out", "exit"} <= nodes
    assert "handle_approval" not in nodes


@pytest.mark.asyncio
async def test_direct_answer_no_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    set_current_user("test-user")
    _install_stub_llm(monkeypatch, [AIMessage(content="Next mower service is due in 12 days.")])

    from langgraph.checkpoint.memory import InMemorySaver
    from agents.maintenance.graph import build_graph
    from agents.state import make_initial_state

    graph = build_graph(checkpointer=InMemorySaver())
    initial = make_initial_state(
        user_message="when is the next mower service?",
        user_id="test-user",
        request_id="req_m1",
    )
    final = await graph.ainvoke(initial, {"configurable": {"thread_id": "t-m1"}})
    assert isinstance(final["messages"][-1], AIMessage)
    assert "12 days" in final["messages"][-1].content
    assert final.get("iteration") == 1


@pytest.mark.asyncio
async def test_auto_retrieval_citation_reaches_llm_system_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """maintenance has retrieve_semantic: true — a retrieved hit should show
    up as a bracketed citation tag in the SystemMessage the stub LLM sees."""
    from langchain_core.messages import SystemMessage

    set_current_user("test-user")
    captured: list = []
    _install_stub_llm(monkeypatch, [AIMessage(content="Water it weekly.")], captured_calls=captured)

    monkeypatch.setattr(
        "core.memory.semantic.SemanticMemory.retrieve",
        lambda self, query, top_k=3: [
            {"id": 7, "content": "Water lemon trees every 7 days.", "score": 0.95,
             "metadata": {"source": "plant_care"}}
        ],
    )

    from langgraph.checkpoint.memory import InMemorySaver
    from agents.maintenance.graph import build_graph
    from agents.state import make_initial_state

    graph = build_graph(checkpointer=InMemorySaver())
    initial = make_initial_state(
        user_message="how often should I water my lemon tree?",
        user_id="test-user", request_id="req_m_rag",
    )
    await graph.ainvoke(initial, {"configurable": {"thread_id": "t-m-rag"}})

    assert len(captured) == 1
    system_msgs = [m for m in captured[0] if isinstance(m, SystemMessage)]
    assert len(system_msgs) == 1
    assert "[plant_care#7]" in system_msgs[0].content
    assert "Water lemon trees every 7 days." in system_msgs[0].content
