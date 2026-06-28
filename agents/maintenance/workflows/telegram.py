"""Telegram workflow: compose and send the monthly home maintenance digest."""

from __future__ import annotations

import os
from datetime import date, timedelta

import httpx

from core.session import get_current_user_id
from db_conn import get_client


def build_monthly_digest() -> str:
    """Query the DB and build a Telegram-formatted monthly maintenance digest."""
    today = date.today()
    month_name = today.strftime("%B %Y")
    week_cutoff = (today + timedelta(days=7)).isoformat()
    month_cutoff = (today + timedelta(days=30)).isoformat()
    today_str = today.isoformat()

    all_upcoming = (
        get_client()
        .table("maintenance_tasks")
        .select("task_name, next_due_date, assets!inner(name)")
        .eq("user_id", get_current_user_id())
        .not_.is_("next_due_date", "null")
        .lte("next_due_date", month_cutoff)
        .order("next_due_date")
        .execute()
        .data
    )

    flat = [
        {"task_name": r["task_name"], "next_due_date": r["next_due_date"], "asset_name": r["assets"]["name"]}
        for r in all_upcoming
    ]

    overdue = [r for r in flat if r["next_due_date"] < today_str]
    due_week = [r for r in flat if today_str <= r["next_due_date"] <= week_cutoff]
    due_month = [r for r in flat if r["next_due_date"] > week_cutoff]

    lines = [f"Home Maintenance Digest - {month_name}\n"]

    if overdue:
        lines.append(f"Overdue ({len(overdue)})")
        for r in overdue[:10]:
            days_ago = (today - date.fromisoformat(r["next_due_date"])).days
            lines.append(f"- {r['asset_name']} - {r['task_name']} ({days_ago}d overdue)")
        if len(overdue) > 10:
            lines.append(f"  ...and {len(overdue) - 10} more")
        lines.append("")
    else:
        lines.append("No overdue tasks\n")

    if due_week:
        lines.append(f"Due this week ({len(due_week)})")
        for r in due_week:
            days = (date.fromisoformat(r["next_due_date"]) - today).days
            suffix = "today" if days == 0 else f"in {days}d"
            lines.append(f"- {r['asset_name']} - {r['task_name']} ({suffix})")
        lines.append("")

    if due_month:
        lines.append(f"Upcoming this month ({len(due_month)})")
        for r in due_month[:8]:
            lines.append(f"- {r['asset_name']} - {r['task_name']} ({r['next_due_date']})")
        if len(due_month) > 8:
            lines.append(f"  ...and {len(due_month) - 8} more")
        lines.append("")

    if not overdue and not due_week and not due_month:
        lines.append("Nothing due this month. Great job staying on top of things!")

    lines.append("Sent by Home Asset Agent")
    return "\n".join(lines)


def send_telegram_message(text: str) -> dict:
    """Send a message via Telegram Bot API."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return {"status": "error", "message": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = httpx.post(
        url,
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=10.0,
    )
    if response.status_code == 200:
        return {"status": "sent", "message_id": response.json().get("result", {}).get("message_id")}
    return {"status": "error", "code": response.status_code, "detail": response.text[:200]}
