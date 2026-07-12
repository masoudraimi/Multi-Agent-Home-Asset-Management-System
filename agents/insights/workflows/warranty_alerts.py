"""Warranty alerts workflow: identify expiring and expired warranties."""

from __future__ import annotations

from datetime import date, timedelta

from core.session import get_current_user_id
from db import get_provider


def get_expiring_warranties(days_ahead: int = 90) -> dict:
    """Return assets with warranties expiring within days_ahead, plus already expired ones."""
    today = date.today()
    cutoff = (today + timedelta(days=days_ahead)).isoformat()
    today_str = today.isoformat()

    all_assets = get_provider().list_assets(get_current_user_id())["assets"]
    all_assets.sort(key=lambda a: a.get("warranty_expiry") or "")

    expired, expiring_soon, valid, unknown = [], [], [], []
    for asset in all_assets:
        expiry = asset.get("warranty_expiry")
        if not expiry:
            unknown.append(asset)
        elif expiry < today_str:
            expired.append({**asset, "days_ago": (today - date.fromisoformat(expiry)).days})
        elif expiry <= cutoff:
            expiring_soon.append({**asset, "days_left": (date.fromisoformat(expiry) - today).days})
        else:
            valid.append({**asset, "days_left": (date.fromisoformat(expiry) - today).days})

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
