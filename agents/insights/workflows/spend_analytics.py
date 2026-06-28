"""Spend analytics workflow: aggregate maintenance cost queries."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from core.session import get_current_user_id
from db_conn import get_client


def get_total_spend_by_category() -> dict:
    """Return total maintenance spend grouped by asset category."""
    uid = get_current_user_id()
    client = get_client()
    assets = client.table("assets").select("id, category").eq("user_id", uid).execute().data
    tasks = client.table("maintenance_tasks").select("asset_id, cost").eq("user_id", uid).execute().data

    asset_category = {a["id"]: a["category"] for a in assets}
    totals: dict[str, dict] = {a["category"]: {"total_cost": 0.0, "task_count": 0} for a in assets}
    for task in tasks:
        cat = asset_category.get(task["asset_id"])
        if cat and cat in totals:
            totals[cat]["total_cost"] += task["cost"] or 0
            totals[cat]["task_count"] += 1

    return {
        "by_category": [
            {"category": cat, "total_cost": round(data["total_cost"], 2), "task_count": data["task_count"]}
            for cat, data in sorted(totals.items(), key=lambda x: x[1]["total_cost"], reverse=True)
        ]
    }


def get_top_spending_assets(n: int = 5) -> dict:
    """Return the N assets with the highest total maintenance spend."""
    uid = get_current_user_id()
    client = get_client()
    assets = client.table("assets").select("id, name, category").eq("user_id", uid).execute().data
    tasks = client.table("maintenance_tasks").select("asset_id, cost").eq("user_id", uid).execute().data

    spend: dict[int, float] = defaultdict(float)
    counts: dict[int, int] = defaultdict(int)
    for task in tasks:
        spend[task["asset_id"]] += task["cost"] or 0
        counts[task["asset_id"]] += 1

    enriched = [
        {
            "id": a["id"], "name": a["name"], "category": a["category"],
            "total_cost": round(spend[a["id"]], 2), "task_count": counts[a["id"]],
        }
        for a in assets
    ]
    enriched.sort(key=lambda x: x["total_cost"], reverse=True)
    return {"top_assets": enriched[:n]}


def get_monthly_spend_trend(months: int = 6) -> dict:
    """Return maintenance spend per month for the last N months."""
    cutoff = (date.today() - timedelta(days=months * 30)).isoformat()
    tasks = (
        get_client()
        .table("maintenance_tasks")
        .select("completed_date, cost")
        .eq("user_id", get_current_user_id())
        .gte("completed_date", cutoff)
        .not_.is_("completed_date", "null")
        .execute()
        .data
    )

    monthly: dict[str, float] = defaultdict(float)
    for task in tasks:
        month = task["completed_date"][:7]  # "YYYY-MM"
        monthly[month] += task["cost"] or 0

    trend = [{"month": m, "spend": round(s, 2)} for m, s in sorted(monthly.items())]
    return {"months": months, "trend": trend}
