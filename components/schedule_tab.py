from datetime import date

import pandas as pd
import streamlit as st

from core.session import get_current_user_id
from db import get_provider

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

    c1, c2, c3 = st.columns(3)
    c1.metric("Overdue", overdue)
    c2.metric("Due within 7 days", due_soon)
    c3.metric("Upcoming", upcoming)

    if df.empty:
        st.success(f"No maintenance tasks due in the next {days} days.")
        return

    for _, row in df.iterrows():
        _task_row(row)


def _task_row(row: pd.Series) -> None:
    urgency = row["urgency"]
    label = _URGENCY_LABEL.get(urgency, urgency)
    days_delta = int(row["days_until_due"])

    if days_delta < 0:
        due_label = f"{abs(days_delta)} days overdue"
    elif days_delta == 0:
        due_label = "Due today"
    else:
        due_label = f"Due in {days_delta} days ({row['next_due_date']})"

    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{row['asset_name']}** — {row['task_name']}")
            st.caption(f"Category: {row.get('category', '')}")
            if row.get("completed_date"):
                st.caption(f"Last done: {row['completed_date']}")
        with col2:
            st.markdown(f"{label}")
            st.caption(due_label)
