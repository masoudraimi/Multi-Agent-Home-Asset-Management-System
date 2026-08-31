"""Tests for agents.insights.report_agent's PydanticAI-backed structured
report tool. Mocks the PydanticAI Agent itself — no real API calls."""

from __future__ import annotations

import pytest


def test_importing_module_does_not_require_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent(...) construction raises immediately if ANTHROPIC_API_KEY is
    unset — importing this module must not trigger construction."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import agents.insights.report_agent as ra
    assert ra._report_agent is None


def test_generate_shareable_report_returns_validated_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    import agents.insights.report_agent as ra

    expected = ra.HomeInsightsReport(
        summary="Your home is in good shape overall.",
        top_recommendations=["Replace HVAC filter", "Renew fridge warranty"],
        risk_items=["Fridge warranty expires in 12 days"],
        estimated_cost_usd=150.0,
    )

    class _FakeResult:
        output = expected

    class _FakeAgent:
        def run_sync(self, notes: str) -> _FakeResult:
            return _FakeResult()

    monkeypatch.setattr(ra, "_get_report_agent", lambda: _FakeAgent())

    result = ra.generate_shareable_report.func(notes="fridge warranty expires soon, HVAC filter overdue")
    assert result["summary"] == "Your home is in good shape overall."
    assert result["top_recommendations"] == ["Replace HVAC filter", "Renew fridge warranty"]
    assert result["estimated_cost_usd"] == 150.0


def test_generate_shareable_report_propagates_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import agents.insights.report_agent as ra

    class _FailingAgent:
        def run_sync(self, notes: str):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(ra, "_get_report_agent", lambda: _FailingAgent())

    with pytest.raises(RuntimeError):
        ra.generate_shareable_report.func(notes="anything")


def test_home_insights_report_defaults() -> None:
    from agents.insights.report_agent import HomeInsightsReport

    report = HomeInsightsReport(summary="ok")
    assert report.top_recommendations == []
    assert report.risk_items == []
    assert report.estimated_cost_usd is None
