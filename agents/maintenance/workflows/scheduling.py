"""Scheduling workflow: policy-based maintenance schedule generation."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from core.session import get_current_user_id
from db import get_provider

POLICIES_PATH = Path(__file__).parent.parent.parent.parent / "knowledge" / "policies" / "maintenance_policies.yaml"

_POLICIES: dict | None = None


def _load_policies() -> dict:
    global _POLICIES
    if _POLICIES is None:
        _POLICIES = yaml.safe_load(POLICIES_PATH.read_text()) if POLICIES_PATH.exists() else {}
    return _POLICIES


def get_policy_schedule(asset_category: str, asset_model: str | None = None) -> list[dict]:
    """Return policy-based tasks for an asset type that has no maintenance history."""
    policies = _load_policies()
    category_key = asset_category.lower().replace(" ", "_")
    tasks = policies.get(category_key, {})
    if not tasks and asset_model:
        model_key = asset_model.lower().split()[0] if asset_model else ""
        tasks = policies.get(category_key, {}).get(model_key, {})
    if not tasks:
        tasks = policies.get(category_key, {}).get("default", {})

    today = date.today()
    result = []
    for task_name, config in tasks.items():
        if not isinstance(config, dict):
            continue
        interval = config.get("interval_days", 365)
        result.append({
            "task": task_name.replace("_", " "),
            "interval_days": interval,
            "notes": config.get("notes", ""),
            "next_due": (today + timedelta(days=interval // 2)).isoformat(),
            "source": "policy",
        })
    return result


def suggest_overdue_assets(days_overdue: int = 0) -> dict:
    """Return assets with tasks that are overdue or have never been serviced."""
    uid = get_current_user_id()
    provider = get_provider()

    upcoming = provider.get_upcoming_maintenance(uid, days_ahead=0)
    overdue = [t for t in upcoming["tasks"] if t["urgency"] == "overdue"]

    all_assets = provider.list_assets(uid)["assets"]
    all_tasks = provider.list_maintenance_tasks(uid)
    serviced_ids = {t["asset_id"] for t in all_tasks}
    never_serviced = [a for a in all_assets if a["id"] not in serviced_ids]

    return {
        "overdue_tasks": len(overdue),
        "never_serviced_assets": len(never_serviced),
        "overdue": overdue[:20],
        "never_serviced": never_serviced[:10],
    }
