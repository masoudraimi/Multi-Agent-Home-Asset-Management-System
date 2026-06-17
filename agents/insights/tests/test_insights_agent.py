"""Unit tests for InsightsAgent and its workflows."""

import pytest


def test_spend_by_category_returns_list():
    from agents.insights.workflows.spend_analytics import get_total_spend_by_category
    result = get_total_spend_by_category()
    assert "by_category" in result
    assert isinstance(result["by_category"], list)


def test_top_spending_assets():
    from agents.insights.workflows.spend_analytics import get_top_spending_assets
    result = get_top_spending_assets(n=3)
    assert "top_assets" in result
    assert len(result["top_assets"]) <= 3


def test_warranty_alerts_structure():
    from agents.insights.workflows.warranty_alerts import get_expiring_warranties
    result = get_expiring_warranties(days_ahead=90)
    assert "summary" in result
    assert "expired" in result["summary"]
    assert "expiring_soon" in result["summary"]
    assert "valid" in result["summary"]


def test_monthly_spend_trend():
    from agents.insights.workflows.spend_analytics import get_monthly_spend_trend
    result = get_monthly_spend_trend(months=3)
    assert "trend" in result
    assert result["months"] == 3
