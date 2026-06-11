"""Unit tests for OrchestratorAgent routing logic."""

import pytest


def test_classify_intent_single_agent(monkeypatch):
    """classify_intent should return a list of valid agent names."""
    import anthropic
    from unittest.mock import MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text='["asset"]')]

    with patch.object(anthropic.Anthropic, "messages", create=True) as mock_messages:
        mock_messages.create.return_value = mock_resp
        from agents.orchestrator.workflows.routing import classify_intent
        with patch("agents.orchestrator.workflows.routing.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            result = classify_intent("What appliances do I have?")
    assert isinstance(result, list)


def test_classify_intent_fallback():
    """classify_intent should fall back to ['asset'] on API error."""
    from unittest.mock import patch
    with patch("agents.orchestrator.workflows.routing.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = Exception("API error")
        from agents.orchestrator.workflows.routing import classify_intent
        result = classify_intent("Some query")
    assert result == ["asset"]


def test_registry_loads_agents():
    from core.registry import AgentRegistry, AgentRegistry
    AgentRegistry.reset()
    reg = AgentRegistry()
    names = reg.all_names()
    assert "asset" in names
    assert "maintenance" in names
    assert "insights" in names
    assert "orchestrator" in names


def test_executor_sequential():
    import asyncio
    from core.executor import WorkflowExecutor

    async def step_a(prior_result=None): return {"a": 1}
    async def step_b(prior_result=None): return {"b": prior_result}

    ex = WorkflowExecutor("test")
    results = asyncio.run(ex.run_sequential("test_wf", [
        ("a", step_a, {}),
        ("b", step_b, {}),
    ]))
    assert results[0] == {"a": 1}
    assert results[1] == {"b": {"a": 1}}


def test_executor_parallel():
    import asyncio
    from core.executor import WorkflowExecutor

    async def task_a(): return "a"
    async def task_b(): return "b"

    ex = WorkflowExecutor("test")
    results = asyncio.run(ex.run_parallel("parallel_wf", [
        ("a", task_a, {}),
        ("b", task_b, {}),
    ]))
    assert set(results) == {"a", "b"}
