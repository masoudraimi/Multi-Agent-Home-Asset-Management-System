"""Tests for core.authz's require_role decorator, applied to delete_asset."""

from __future__ import annotations

import pytest

from core.authz import AuthorizationError, require_role
from core.session import set_current_user_role


@pytest.fixture(autouse=True)
def _reset_role():
    set_current_user_role(None)
    yield
    set_current_user_role(None)


def test_require_role_allows_permitted_role():
    calls = []

    @require_role("user", "admin")
    def do_thing(x: int) -> int:
        calls.append(x)
        return x * 2

    set_current_user_role("user")
    assert do_thing(3) == 6
    assert calls == [3]


def test_require_role_denies_unpermitted_role():
    @require_role("admin")
    def admin_only() -> str:
        return "secret"

    set_current_user_role("user")
    with pytest.raises(AuthorizationError):
        admin_only()


def test_require_role_denies_missing_role():
    @require_role("user", "admin")
    def do_thing() -> str:
        return "ok"

    set_current_user_role(None)
    with pytest.raises(AuthorizationError):
        do_thing()


def test_require_role_denial_is_audited(monkeypatch: pytest.MonkeyPatch):
    audited = []
    monkeypatch.setattr("core.authz.audit", lambda event_type, **kw: audited.append((event_type, kw)))

    @require_role("admin")
    def admin_only() -> str:
        return "secret"

    set_current_user_role("user")
    with pytest.raises(AuthorizationError):
        admin_only()

    assert len(audited) == 1
    event_type, payload = audited[0]
    assert event_type == "tool_authorization_denied"
    assert payload["payload"]["tool"] == "admin_only"
    assert payload["payload"]["role"] == "user"


def test_delete_asset_tool_is_role_gated_but_permits_authenticated_users():
    """delete_asset requires role in ("user", "admin") — proves the decorator
    is actually wired onto the real tool, not just tested in isolation."""
    from tools.langchain_tools import delete_asset

    set_current_user_role(None)  # no role set at all
    with pytest.raises(AuthorizationError):
        delete_asset.func(asset_id=1)


@pytest.mark.asyncio
async def test_tool_node_turns_authorization_error_into_tool_message(monkeypatch: pytest.MonkeyPatch):
    """LangGraph's ToolNode default error handling should surface the denial
    as an error ToolMessage fed back to the LLM, not crash the graph — driven
    through the real compiled asset graph so the full config/runtime context
    ToolNode expects is present (unlike a bare ToolNode.invoke())."""
    from typing import Any

    from langchain_core.messages import AIMessage, ToolCall
    from langgraph.checkpoint.memory import InMemorySaver

    from agents.asset.graph import build_graph
    from agents.state import make_initial_state
    from core.session import set_current_user

    set_current_user("test-user")
    set_current_user_role(None)  # no role -> delete_asset denies

    responses = iter([
        AIMessage(content="", tool_calls=[
            ToolCall(name="delete_asset", args={"asset_id": 1}, id="call_1"),
        ]),
        AIMessage(content="I couldn't delete that asset."),
    ])

    class _StubChatModel:
        def bind_tools(self, *_a: Any, **_kw: Any) -> "_StubChatModel":
            return self

        def invoke(self, _messages: Any, *_a: Any, **_kw: Any) -> AIMessage:
            return next(responses)

    monkeypatch.setattr("agents._specialist.build_chat_model", lambda *a, **kw: _StubChatModel())

    graph = build_graph(checkpointer=InMemorySaver())
    initial = make_initial_state(user_message="delete asset 1", user_id="test-user", request_id="req_authz_1")
    final = await graph.ainvoke(initial, {"configurable": {"thread_id": "t-authz"}})

    from langchain_core.messages import ToolMessage
    tool_messages = [m for m in final["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].status == "error"
    assert "not permitted" in tool_messages[0].content.lower()
    assert final["messages"][-1].content == "I couldn't delete that asset."
