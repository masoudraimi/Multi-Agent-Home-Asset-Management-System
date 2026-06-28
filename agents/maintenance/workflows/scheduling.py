"""Scheduling workflow: policy-based maintenance schedule generation."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from core.session import get_current_user_id
from db_conn import get_client

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
    today = date.today().isoformat()
    uid = get_current_user_id()
    client = get_client()

    overdue_rows = (
        client.table("maintenance_tasks")
        .select("*, assets!inner(name, category)")
        .eq("user_id", uid)
        .not_.is_("next_due_date", "null")
        .lt("next_due_date", today)
        .order("next_due_date")
        .execute()
        .data
    )
    overdue = []
    for row in overdue_rows:
        d = {k: v for k, v in row.items() if k != "assets"}
        d["asset_name"] = row["assets"]["name"]
        d["category"] = row["assets"]["category"]
        overdue.append(d)

    all_assets = client.table("assets").select("id, name, category, created_at").eq("user_id", uid).execute().data
    serviced_ids = {
        row["asset_id"]
        for row in client.table("maintenance_tasks").select("asset_id").eq("user_id", uid).execute().data
    }
    never_serviced = [a for a in all_assets if a["id"] not in serviced_ids]

    return {
        "overdue_tasks": len(overdue),
        "never_serviced_assets": len(never_serviced),
        "overdue": overdue[:20],
        "never_serviced": never_serviced[:10],
    }
