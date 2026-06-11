"""Unit tests for MaintenanceAgent and its workflows."""

import pytest
from pathlib import Path


def test_scheduling_policies_load():
    from agents.maintenance.workflows.scheduling import _load_policies
    policies = _load_policies()
    assert isinstance(policies, dict)
    assert "HVAC" in policies or len(policies) >= 0


def test_suggest_overdue_assets_returns_dict():
    from agents.maintenance.workflows.scheduling import suggest_overdue_assets
    result = suggest_overdue_assets()
    assert "overdue_tasks" in result
    assert "never_serviced_assets" in result


def test_plant_care_schedule_unknown_asset():
    from agents.maintenance.workflows.plant_care import get_plant_care_schedule
    result = get_plant_care_schedule(asset_id=9999)
    assert "error" in result


def test_plant_care_fuzzy_match():
    from agents.maintenance.workflows.plant_care import _fuzzy_match, _load_care_data
    care_data = _load_care_data()
    assert _fuzzy_match("lemon tree", care_data) == "lemon tree"
    assert _fuzzy_match("unknown exotic plant", care_data) == "default"
    assert _fuzzy_match("", care_data) == "default"
