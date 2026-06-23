"""Asset suggestion workflow: gap analysis vs home asset checklist."""

from __future__ import annotations

import json
from pathlib import Path

from db_conn import get_client

CHECKLIST_PATH = Path(__file__).parent.parent.parent.parent / "data" / "home_asset_checklist.json"


def suggest_missing_assets() -> dict:
    """Compare current assets against a comprehensive home asset checklist and surface gaps."""
    checklist = json.loads(CHECKLIST_PATH.read_text())

    rows = get_client().table("assets").select("name, category").execute().data
    existing_names = {row["name"].lower() for row in rows}

    suggestions = []
    for category, items in checklist.items():
        for item in items:
            item_name_lower = item["name"].lower()
            already_tracked = any(
                item_name_lower in existing or existing in item_name_lower
                for existing in existing_names
            )
            if not already_tracked:
                suggestions.append({
                    "category": category,
                    "name": item["name"],
                    "priority": item["priority"],
                    "reason": item["reason"],
                })

    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda x: (priority_order.get(x["priority"], 3), x["category"]))

    high = [s for s in suggestions if s["priority"] == "high"]
    medium = [s for s in suggestions if s["priority"] == "medium"]
    low = [s for s in suggestions if s["priority"] == "low"]

    return {
        "total_gaps": len(suggestions),
        "high_priority": len(high),
        "medium_priority": len(medium),
        "low_priority": len(low),
        "suggestions": suggestions,
        "summary": f"Found {len(suggestions)} potentially untracked assets ({len(high)} high priority).",
    }
