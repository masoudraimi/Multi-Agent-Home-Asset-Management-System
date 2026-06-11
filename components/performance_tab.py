import json
from pathlib import Path

import pandas as pd
import streamlit as st

RESULTS_PATH = Path(__file__).parent.parent / "eval" / "results.json"
BENCHMARKS_ROOT = Path(__file__).parent.parent / "eval" / "benchmarks"

_TIER_ORDER = ["simple", "moderate", "complex"]
_AGENTS = ["asset_agent", "maintenance_agent", "orchestrator"]


def render_performance_tab() -> None:
    st.subheader("Agent Performance")

    # Live turn metrics from session
    _render_session_metrics()

    st.divider()

    # Per-agent benchmark scenarios (static overview from JSON files)
    st.subheader("Agent Benchmarks")
    _render_agent_benchmarks()

    st.divider()

    # Offline benchmark results (from eval/run_eval.py)
    st.subheader("Benchmark Run Results")
    if not RESULTS_PATH.exists():
        st.info(
            "No benchmark results yet. Run `uv run python eval/run_eval.py` to generate them."
        )
        return

    data = json.loads(RESULTS_PATH.read_text())
    _render_summary(data["summary"])
    _render_results_table(data["results"])


def _render_agent_benchmarks() -> None:
    """Show benchmark scenario counts and sample queries per agent."""
    tabs = st.tabs([a.replace("_", " ").title() for a in _AGENTS])
    for tab, agent_name in zip(tabs, _AGENTS):
        with tab:
            bench_path = BENCHMARKS_ROOT / f"{agent_name}.json"
            if not bench_path.exists():
                st.caption("No benchmark file found.")
                continue
            scenarios = json.loads(bench_path.read_text())
            st.metric("Scenarios", len(scenarios))
            rows = [
                {
                    "ID": s["id"],
                    "Query": s["query"],
                    "Expected Tools": ", ".join(s.get("expected_tools", [])) or "(none)",
                    "Description": s.get("description", ""),
                }
                for s in scenarios
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_session_metrics() -> None:
    st.subheader("This Session")
    metrics_history = st.session_state.get("turn_metrics", [])

    if not metrics_history:
        st.caption("No turns yet — start chatting to see live metrics.")
        return

    df = pd.DataFrame(metrics_history)
    df.index = [f"Turn {i+1}" for i in range(len(df))]

    c1, c2, c3 = st.columns(3)
    c1.metric("Turns", len(df))
    c2.metric("Avg latency", f"{int(df['latency_ms'].mean())}ms")
    c3.metric("Avg tool calls / turn", f"{df['tool_call_count'].mean():.1f}")

    st.bar_chart(df[["latency_ms", "tokens"]].rename(columns={
        "latency_ms": "Latency (ms)",
        "tokens": "Tokens",
    }))


def _render_summary(summary: dict) -> None:
    rows = []
    for tier in _TIER_ORDER:
        if tier not in summary:
            continue
        s = summary[tier]
        rows.append({
            "Tier": tier.capitalize(),
            "Accuracy": f"{s['accuracy']*100:.0f}%",
            "Passed": f"{s['passed']}/{s['total']}",
            "Avg Latency (ms)": s["avg_latency_ms"],
            "Avg Tokens": s["avg_tokens"],
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_results_table(results: list) -> None:
    st.subheader("Per-Scenario Results")
    tier_filter = st.selectbox(
        "Filter by tier", ["All", "simple", "moderate", "complex"], key="perf_tier_filter"
    )
    df = pd.DataFrame(results)
    if tier_filter != "All":
        df = df[df["tier"] == tier_filter]

    display = df[[
        "id", "tier", "passed", "tool_hit", "keyword_score",
        "tool_call_count", "latency_ms", "tokens", "query"
    ]].rename(columns={
        "id": "ID", "tier": "Tier", "passed": "Pass",
        "tool_hit": "Tools OK", "keyword_score": "KW Score",
        "tool_call_count": "Tool Calls", "latency_ms": "Latency (ms)",
        "tokens": "Tokens", "query": "Query",
    })

    def _highlight(val: bool) -> str:
        return "background-color: #c8e6c9" if val else "background-color: #ffcdd2"

    styled = display.style.map(_highlight, subset=["Pass", "Tools OK"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
