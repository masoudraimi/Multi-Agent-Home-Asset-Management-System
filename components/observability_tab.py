"""Observability tab: live OTel spans and audit log viewer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

AUDIT_LOG_PATH = Path(__file__).parent.parent / "data" / "audit.jsonl"


def render_observability_tab() -> None:
    st.subheader("Observability")

    col_spans, col_audit = st.columns([3, 2])

    with col_spans:
        _render_spans()

    with col_audit:
        _render_audit_log()


def _render_spans() -> None:
    st.markdown("#### Recent Spans")
    try:
        from core.observability import get_recent_spans
        spans = get_recent_spans(limit=100)
    except Exception as exc:
        st.warning(f"Could not load spans: {exc}")
        return

    if not spans:
        st.caption("No spans recorded yet. Start a conversation to see traces.")
        return

    df = pd.DataFrame(spans)

    agent_options = ["All"] + sorted(df["agent"].dropna().unique().tolist())
    selected_agent = st.selectbox("Filter by agent", agent_options, key="obs_agent_filter")
    if selected_agent != "All":
        df = df[df["agent"] == selected_agent]

    status_color = {"OK": "#c8e6c9", "ERROR": "#ffcdd2", "UNSET": "#fff9c4"}

    display = df[["name", "agent", "duration_ms", "status"]].rename(columns={
        "name": "Span",
        "agent": "Agent",
        "duration_ms": "Duration (ms)",
        "status": "Status",
    })

    def _highlight_status(val: str) -> str:
        return f"background-color: {status_color.get(val, '')}"

    styled = display.style.map(_highlight_status, subset=["Status"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    if st.checkbox("Show span attributes", key="obs_show_attrs"):
        selected_idx = st.number_input(
            "Span index (0-based)", min_value=0, max_value=max(0, len(spans) - 1),
            value=0, step=1, key="obs_span_idx"
        )
        if 0 <= selected_idx < len(spans):
            st.json(spans[selected_idx].get("attributes", {}))

    # Summary metrics
    if len(df) > 0:
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total spans", len(df))
        c2.metric("Avg duration", f"{int(df['duration_ms'].mean())}ms")
        error_count = (df["status"] == "ERROR").sum()
        c3.metric("Errors", int(error_count))


def _render_audit_log() -> None:
    st.markdown("#### Audit Log")

    if not AUDIT_LOG_PATH.exists():
        st.caption("No audit events yet.")
        return

    lines = AUDIT_LOG_PATH.read_text().strip().splitlines()
    if not lines:
        st.caption("No audit events yet.")
        return

    events = []
    for line in lines[-50:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    events.reverse()

    for ev in events[:20]:
        event_type = ev.get("event_type", "unknown")
        ts = ev.get("timestamp", "")[:19].replace("T", " ")
        agent = ev.get("data", {}).get("agent_name", "")
        label = f"`{ts}` **{event_type}**" + (f" — {agent}" if agent else "")
        with st.expander(label, expanded=False):
            st.json(ev.get("data", {}))
