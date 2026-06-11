"""Scheduling workflow: policy-based maintenance schedule generation.

Uses maintenance_policies.yaml as a fallback when an asset has no recorded history.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import yaml

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "home_assets.db"
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
        next_due = (today + timedelta(days=interval // 2)).isoformat()
        result.append({
            "task": task_name.replace("_", " "),
            "interval_days": interval,
            "notes": config.get("notes", ""),
            "next_due": next_due,
            "source": "policy",
        })
    return result


def suggest_overdue_assets(days_overdue: int = 0) -> dict:
    """Return assets with tasks that are overdue or have never been serviced."""
    today = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    overdue_rows = conn.execute(
        """SELECT mt.*, a.name as asset_name, a.category
           FROM maintenance_tasks mt
           JOIN assets a ON mt.asset_id = a.id
           WHERE mt.next_due_date IS NOT NULL
             AND mt.next_due_date < ?
           ORDER BY mt.next_due_date ASC""",
        (today,),
    ).fetchall()

    all_assets = conn.execute(
        "SELECT id, name, category, created_at FROM assets"
    ).fetchall()
    assets_with_tasks = {
        row["asset_id"]
        for row in conn.execute("SELECT DISTINCT asset_id FROM maintenance_tasks").fetchall()
    }
    conn.close()

    overdue = [dict(r) for r in overdue_rows]
    never_serviced = [
        dict(a) for a in all_assets
        if a["id"] not in assets_with_tasks
    ]

    return {
        "overdue_tasks": len(overdue),
        "never_serviced_assets": len(never_serviced),
        "overdue": overdue[:20],
        "never_serviced": never_serviced[:10],
    }
