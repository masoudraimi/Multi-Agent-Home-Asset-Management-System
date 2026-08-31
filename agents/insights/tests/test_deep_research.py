"""Tests for agents.insights.deep_research's tool wrapper logic.

Mocks the compiled deep-agent graph itself (`_get_deep_agent`) rather than
exercising a real deepagents run — this tests the wrapper's message
extraction and step counting, not the deepagents library or a live model.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolCall, ToolMessage


def test_importing_module_does_not_require_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deep agent must be built lazily — importing this module (which
    happens at agents/insights/graph.py import time) should never construct
    a chat model, which would need real API credentials."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    import agents.insights.deep_research as dr
    assert dr._deep_agent is None


def test_deep_research_analysis_extracts_final_answer_and_step_count(monkeypatch: pytest.MonkeyPatch) -> None:
    import agents.insights.deep_research as dr

    fake_messages = [
        HumanMessage(content="why is my bill high"),
        AIMessage(content="", tool_calls=[ToolCall(name="list_assets", args={}, id="c1")]),
        ToolMessage(content="{}", tool_call_id="c1", name="list_assets"),
        AIMessage(content="", tool_calls=[ToolCall(name="get_asset_history", args={"asset_id": 1}, id="c2")]),
        ToolMessage(content="{}", tool_call_id="c2", name="get_asset_history"),
        AIMessage(content="Your HVAC system accounts for most of the increase."),
    ]

    class _FakeDeepAgent:
        def invoke(self, input_: dict) -> dict:
            return {"messages": fake_messages}

    monkeypatch.setattr(dr, "_get_deep_agent", lambda: _FakeDeepAgent())

    result = dr.deep_research_analysis.func(query="why is my bill high")
    assert result["analysis"] == "Your HVAC system accounts for most of the increase."
    assert result["steps_taken"] == 2


def test_deep_research_analysis_propagates_and_logs_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import agents.insights.deep_research as dr

    class _FailingDeepAgent:
        def invoke(self, input_: dict) -> dict:
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(dr, "_get_deep_agent", lambda: _FailingDeepAgent())

    with pytest.raises(RuntimeError):
        dr.deep_research_analysis.func(query="anything")


def test_research_tool_names_are_all_real_tools() -> None:
    from tools.langchain_tools import TOOLS_BY_NAME
    import agents.insights.deep_research as dr

    for name in dr._RESEARCH_TOOL_NAMES:
        assert name in TOOLS_BY_NAME
