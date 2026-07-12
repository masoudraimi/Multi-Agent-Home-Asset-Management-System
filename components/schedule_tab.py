import html
from datetime import date

import pandas as pd
import streamlit as st

from core.session import get_current_user_id
from db import get_provider

_URGENCY_COLOUR = {
    "overdue": "#d32f2f",
    "due_soon": "#f57c00",
    "upcoming": "#388e3c",
}

_URGENCY_LABEL = {
    "overdue": "🔴 Overdue",
    "due_soon": "🟠 Due soon",
    "upcoming": "🟢 Upcoming",
}

_URGENCY_ORDER = {"overdue": 0, "due_soon": 1, "upcoming": 2}


def _load_upcoming(days: int) -> pd.DataFrame:
    result = get_provider().get_upcoming_maintenance(get_current_user_id(), days)
    if not result["tasks"]:
        return pd.DataFrame()
    df = pd.DataFrame(result["tasks"])
    df["urgency_order"] = df["urgency"].map(_URGENCY_ORDER)
    return df.sort_values(["urgency_order", "next_due_date"])


def render_schedule_tab() -> None:
    st.subheader("Maintenance Schedule")

    days = st.slider("Show tasks due within (days)", 7, 365, 60, key="schedule_days")
    df = _load_upcoming(days)

    overdue = len(df[df["urgency"] == "overdue"]) if not df.empty else 0
    due_soon = len(df[df["urgency"] == "due_soon"]) if not df.empty else 0
    upcoming = len(df[df["urgency"] == "upcoming"]) if not df.empty else 0

    # Styled metric row
    st.html(f"""
    <div style="
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 12px; margin: 12px 0 20px;
        font-family: system-ui, sans-serif;
    ">
        <div style="
            background: linear-gradient(135deg, rgba(211,47,47,0.15), rgba(211,47,47,0.05));
            border: 1px solid rgba(211,47,47,0.35); border-radius: 12px;
            padding: 16px; text-align: center;
        ">
            <div style="font-size: 30px; font-weight: 700; color: #ef5350;">{overdue}</div>
            <div style="font-size: 11px; color: rgba(255,255,255,0.45); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px;">Overdue</div>
        </div>
        <div style="
            background: linear-gradient(135deg, rgba(245,124,0,0.15), rgba(245,124,0,0.05));
            border: 1px solid rgba(245,124,0,0.35); border-radius: 12px;
            padding: 16px; text-align: center;
        ">
            <div style="font-size: 30px; font-weight: 700; color: #ffa726;">{due_soon}</div>
            <div style="font-size: 11px; color: rgba(255,255,255,0.45); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px;">Due this week</div>
        </div>
        <div style="
            background: linear-gradient(135deg, rgba(56,142,60,0.15), rgba(56,142,60,0.05));
            border: 1px solid rgba(56,142,60,0.35); border-radius: 12px;
            padding: 16px; text-align: center;
        ">
            <div style="font-size: 30px; font-weight: 700; color: #66bb6a;">{upcoming}</div>
            <div style="font-size: 11px; color: rgba(255,255,255,0.45); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px;">Upcoming</div>
        </div>
    </div>
    """)

    if df.empty:
        st.success(f"No maintenance tasks due in the next {days} days.")
        return

    for _, row in df.iterrows():
        _task_row(row)


def _task_row(row: pd.Series) -> None:
    urgency = row["urgency"]
    colour = _URGENCY_COLOUR.get(urgency, "#6C63FF")
    label = _URGENCY_LABEL.get(urgency, urgency)
    days_delta = int(row["days_until_due"])

    if days_delta < 0:
        due_label = f"{abs(days_delta)}d overdue"
    elif days_delta == 0:
        due_label = "Due today"
    else:
        due_label = f"in {days_delta}d"

    asset_name = html.escape(str(row.get("asset_name", "")))
    task_name = html.escape(str(row.get("task_name", "")))
    category = html.escape(str(row.get("category", "")))
    last_done = f"Last: {row['completed_date']}" if row.get("completed_date") else "Never serviced"

    st.html(f"""
    <div style="
        display: flex; justify-content: space-between; align-items: center;
        border-left: 4px solid {colour};
        background: rgba(255,255,255,0.025);
        border-radius: 0 10px 10px 0;
        padding: 13px 18px; margin: 6px 0;
        font-family: system-ui, sans-serif;
        transition: background 0.15s;
    ">
        <div style="flex: 1; min-width: 0;">
            <div style="font-weight: 600; font-size: 14px; color: #E6EDF3; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                {asset_name} &mdash; {task_name}
            </div>
            <div style="font-size: 11px; color: rgba(255,255,255,0.4);">
                <span style="
                    background: rgba(255,255,255,0.08);
                    border-radius: 4px; padding: 1px 6px;
                    margin-right: 6px;
                ">{category}</span>
                {html.escape(last_done)}
            </div>
        </div>
        <div style="text-align: right; flex-shrink: 0; margin-left: 16px;">
            <div style="font-size: 13px; font-weight: 600; color: {colour};">{label}</div>
            <div style="font-size: 11px; color: rgba(255,255,255,0.35); margin-top: 2px;">{html.escape(due_label)}</div>
        </div>
    </div>
    """)
