"""Warranty alerts workflow: identify expiring and expired warranties."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "home_assets.db"


def get_expiring_warranties(days_ahead: int = 90) -> dict:
    """Return assets with warranties expiring within days_ahead, plus already expired ones."""
    today = date.today()
    cutoff = (today + timedelta(days=days_ahead)).isoformat()
    today_str = today.isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    all_assets = conn.execute(
        "SELECT id, name, category, warranty_expiry, purchase_price FROM assets ORDER BY warranty_expiry"
    ).fetchall()
    conn.close()

    expired = []
    expiring_soon = []
    valid = []
    unknown = []

    for asset in all_assets:
        expiry = asset["warranty_expiry"]
        if not expiry:
            unknown.append(dict(asset))
        elif expiry < today_str:
            days_ago = (today - date.fromisoformat(expiry)).days
            expired.append({**dict(asset), "days_ago": days_ago})
        elif expiry <= cutoff:
            days_left = (date.fromisoformat(expiry) - today).days
            expiring_soon.append({**dict(asset), "days_left": days_left})
        else:
            days_left = (date.fromisoformat(expiry) - today).days
            valid.append({**dict(asset), "days_left": days_left})

    return {
        "as_of": today_str,
        "days_ahead": days_ahead,
        "summary": {
            "expired": len(expired),
            "expiring_soon": len(expiring_soon),
            "valid": len(valid),
            "unknown": len(unknown),
        },
        "expired": expired,
        "expiring_soon": expiring_soon,
        "valid": valid[:10],
        "unknown": unknown[:10],
    }
