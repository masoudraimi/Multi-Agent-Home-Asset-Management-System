import json

import streamlit as st

from agent.context import ConversationContext
from agent.runner import run_turn

_URGENCY_COLOUR = {
    "overdue": "#d32f2f",
    "due_soon": "#f57c00",
    "upcoming": "#388e3c",
}


def _tool_call_card(event: dict, index: int) -> None:
    args_str = json.dumps(event["args"], indent=2)
    with st.expander(f"Step {index}: `{event['name']}`", expanded=False):
        st.code(args_str, language="json")


def _tool_result_card(event: dict, index: int) -> None:
    with st.expander(f"Step {index} result", expanded=False):
        st.json(event["result"])


def render_chat_tab() -> None:
    if "context" not in st.session_state:
        st.session_state.context = ConversationContext()
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "turn_metrics" not in st.session_state:
        st.session_state.turn_metrics = []

    ctx: ConversationContext = st.session_state.context

    # Render history
    for entry in st.session_state.chat_messages:
        with st.chat_message(entry["role"]):
            if entry["role"] == "user":
                st.markdown(entry["content"])
            else:
                _render_assistant_entry(entry)

    if prompt := st.chat_input("Ask about your home assets…"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            tool_events: list[dict] = []
            answer = ""
            metrics: dict = {}
            step = 0

            result_placeholder = st.empty()

            for event in run_turn(prompt, ctx):
                if event["type"] == "tool_call":
                    step += 1
                    tool_events.append({"call": event, "result": None, "step": step})
                    _tool_call_card(event, step)

                elif event["type"] == "tool_result":
                    for t in tool_events:
                        if t["call"]["call_id"] == event["call_id"]:
                            t["result"] = event
                            _tool_result_card(event, t["step"])
                            break

                elif event["type"] == "assistant_text":
                    answer = event["content"]
                    result_placeholder.markdown(answer)

                elif event["type"] == "metrics":
                    metrics = event

            if metrics:
                st.caption(
                    f"Tools: {metrics['tool_call_count']} calls · "
                    f"{metrics['latency_ms']}ms · "
                    f"{metrics['tokens']} tokens · "
                    f"ctx≈{ctx.token_estimate} tokens"
                )

        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": answer,
            "tool_events": tool_events,
            "metrics": metrics,
        })
        if metrics:
            st.session_state.turn_metrics.append(metrics)

        st.rerun()


def _render_assistant_entry(entry: dict) -> None:
    for te in entry.get("tool_events", []):
        _tool_call_card(te["call"], te["step"])
        if te["result"]:
            _tool_result_card(te["result"], te["step"])
    st.markdown(entry["content"])
    m = entry.get("metrics", {})
    if m:
        st.caption(
            f"Tools: {m.get('tool_call_count', 0)} calls · "
            f"{m.get('latency_ms', 0)}ms · "
            f"{m.get('tokens', 0)} tokens"
        )
