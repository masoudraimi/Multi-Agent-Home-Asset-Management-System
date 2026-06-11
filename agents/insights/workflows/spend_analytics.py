"""Spend analytics workflow: aggregate maintenance cost queries."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "home_assets.db"


def get_total_spend_by_category() -> dict:
    """Return total maintenance spend grouped by asset category."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT a.category, SUM(COALESCE(mt.cost, 0)) as total_cost, COUNT(mt.id) as task_count
           FROM assets a
           LEFT JOIN maintenance_tasks mt ON a.id = mt.asset_id
           GROUP BY a.category
           ORDER BY total_cost DESC"""
    ).fetchall()
    conn.close()
    return {
        "by_category": [
            {"category": r["category"], "total_cost": round(r["total_cost"], 2), "task_count": r["task_count"]}
            for r in rows
        ]
    }


def get_top_spending_assets(n: int = 5) -> dict:
    """Return the N assets with the highest total maintenance spend."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT a.id, a.name, a.category, SUM(COALESCE(mt.cost, 0)) as total_cost, COUNT(mt.id) as task_count
           FROM assets a
           LEFT JOIN maintenance_tasks mt ON a.id = mt.asset_id
           GROUP BY a.id
           ORDER BY total_cost DESC
           LIMIT ?""",
        (n,),
    ).fetchall()
    conn.close()
    return {
        "top_assets": [
            {
                "id": r["id"], "name": r["name"], "category": r["category"],
                "total_cost": round(r["total_cost"], 2), "task_count": r["task_count"],
            }
            for r in rows
        ]
    }


def get_monthly_spend_trend(months: int = 6) -> dict:
    """Return maintenance spend per month for the last N months."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cutoff = (date.today() - timedelta(days=months * 30)).isoformat()
    rows = conn.execute(
        """SELECT strftime('%Y-%m', completed_date) as month, SUM(COALESCE(cost, 0)) as total
           FROM maintenance_tasks
           WHERE completed_date >= ?
           GROUP BY month
           ORDER BY month ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return {
        "months": months,
        "trend": [{"month": r["month"], "spend": round(r["total"], 2)} for r in rows],
    }
