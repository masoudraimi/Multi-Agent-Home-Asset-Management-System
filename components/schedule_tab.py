import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "data" / "home_assets.db"

_URGENCY_LABEL = {
    "overdue": "🔴 Overdue",
    "due_soon": "🟠 Due soon",
    "upcoming": "🟢 Upcoming",
}

_URGENCY_ORDER = {"overdue": 0, "due_soon": 1, "upcoming": 2}


def _load_upcoming(days: int) -> pd.DataFrame:
    today = date.today()
    cutoff = (today + timedelta(days=days)).isoformat()
    today_str = today.isoformat()

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """SELECT mt.id, a.name as asset_name, a.category, mt.task_name,
                  mt.next_due_date, mt.completed_date, mt.interval_days
           FROM maintenance_tasks mt
           JOIN assets a ON mt.asset_id = a.id
           WHERE mt.next_due_date IS NOT NULL
             AND mt.next_due_date <= ?
           ORDER BY mt.next_due_date ASC""",
        conn,
        params=(cutoff,),
    )
    conn.close()

    if df.empty:
        return df

    df["days_until_due"] = df["next_due_date"].apply(
        lambda d: (date.fromisoformat(d) - today).days
    )

    def _urgency(days_delta: int) -> str:
        if days_delta < 0:
            return "overdue"
        elif days_delta <= 7:
            return "due_soon"
        return "upcoming"

    df["urgency"] = df["days_until_due"].apply(_urgency)
    df["urgency_order"] = df["urgency"].map(_URGENCY_ORDER)
    df = df.sort_values(["urgency_order", "next_due_date"])
    return df


def render_schedule_tab() -> None:
    st.subheader("Maintenance Schedule")

    days = st.slider("Show tasks due within (days)", 7, 365, 60, key="schedule_days")
    df = _load_upcoming(days)

    overdue = len(df[df["urgency"] == "overdue"]) if not df.empty else 0
    due_soon = len(df[df["urgency"] == "due_soon"]) if not df.empty else 0
    upcoming = len(df[df["urgency"] == "upcoming"]) if not df.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Overdue", overdue, delta=None)
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
            st.caption(f"Category: {row['category']}")
            if row.get("completed_date"):
                st.caption(f"Last done: {row['completed_date']}")
        with col2:
            st.markdown(f"{label}")
            st.caption(due_label)
