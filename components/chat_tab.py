import html
import json

import streamlit as st

from agent.context import ConversationContext
from agent.runner import run_turn
from core.observability import audit_log

_URGENCY_COLOUR = {
    "overdue": "#d32f2f",
    "due_soon": "#f57c00",
    "upcoming": "#388e3c",
}

_TOOL_ICONS = {
    "add_asset": "📦",
    "list_assets": "📋",
    "search_assets": "🔍",
    "update_asset": "✏️",
    "log_maintenance": "🔧",
    "get_upcoming_maintenance": "🗓",
    "get_asset_history": "📜",
    "get_onboarding_questions": "❓",
    "review_asset_draft": "🔎",
    "get_plant_care_schedule": "🌿",
    "suggest_missing_assets": "💡",
    "get_expiring_warranties": "⚠️",
}


def _subscribe_approval_events() -> None:
    """Register EventBus handler for HumanApprovalRequested (once per session)."""
    if st.session_state.get("_approval_handler_registered"):
        return
    try:
        from core.event_bus import EventBus
        from core.events import HumanApprovalRequested

        bus = EventBus()

        def _on_approval(event: HumanApprovalRequested) -> None:
            pending = st.session_state.setdefault("pending_approvals", {})
            pending[event.request_id] = {
                "request_id": event.request_id,
                "agent_name": event.agent_name,
                "action_description": event.action_description,
                "payload": event.payload,
                "timestamp": event.timestamp,
            }

        bus.subscribe(HumanApprovalRequested, _on_approval)
        st.session_state["_approval_handler_registered"] = True
    except Exception:
        pass


def _render_approval_cards() -> None:
    """Render pending human approval confirmation cards above the chat input."""
    pending: dict = st.session_state.get("pending_approvals", {})
    if not pending:
        return

    for request_id, approval in list(pending.items()):
        st.markdown("---")
        # Styled approval banner
        st.html(f"""
        <div style="
            border-left: 4px solid #f57c00;
            background: linear-gradient(135deg, rgba(245,124,0,0.12), rgba(245,124,0,0.04));
            border-radius: 0 12px 12px 0;
            padding: 14px 18px;
            margin-bottom: 8px;
            font-family: system-ui, sans-serif;
        ">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                <span style="font-size: 18px;">⚠️</span>
                <span style="font-weight: 700; font-size: 15px; color: #f57c00;">Action requires your approval</span>
            </div>
            <div style="font-size: 12px; color: rgba(255,255,255,0.45); margin-bottom: 8px;">
                Agent: <code style="background: rgba(255,255,255,0.1); border-radius: 4px; padding: 1px 6px;">{html.escape(approval['agent_name'])}</code>
                &nbsp;·&nbsp; ID: <code style="background: rgba(255,255,255,0.1); border-radius: 4px; padding: 1px 6px;">{html.escape(request_id[:8])}&hellip;</code>
            </div>
            <div style="font-size: 14px; color: #E6EDF3;">{html.escape(approval['action_description'])}</div>
        </div>
        """)
        with st.expander("View payload", expanded=False):
            st.json(approval["payload"])

        col_confirm, col_cancel, col_spacer = st.columns([1, 1, 3])
        if col_confirm.button("✓ Confirm", key=f"approve_{request_id}", type="primary"):
            audit_log("approval_confirmed", {
                "request_id": request_id,
                "agent_name": approval["agent_name"],
                "payload": approval["payload"],
            })
            del pending[request_id]
            st.session_state.chat_messages.append({
                "role": "user",
                "content": "__approval_confirmed__",
            })
            st.rerun()
        if col_cancel.button("✕ Cancel", key=f"cancel_{request_id}"):
            audit_log("approval_cancelled", {
                "request_id": request_id,
                "agent_name": approval["agent_name"],
            })
            del pending[request_id]
            st.session_state.chat_messages.append({
                "role": "user",
                "content": "__approval_cancelled__",
            })
            st.rerun()


def _maybe_process_approval(ctx: ConversationContext) -> None:
    """If the last chat message is __approval_confirmed__, auto-trigger the agent turn."""
    msgs = st.session_state.get("chat_messages", [])
    if not msgs or msgs[-1]["content"] != "__approval_confirmed__":
        return

    with st.chat_message("assistant"):
        tool_events: list[dict] = []
        answer = ""
        metrics: dict = {}
        step = 0
        result_placeholder = st.empty()

        for event in run_turn("__approval_confirmed__", ctx):
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

    st.session_state.chat_messages.append({
        "role": "assistant",
        "content": answer,
        "tool_events": tool_events,
        "metrics": metrics,
    })
    if metrics:
        st.session_state.turn_metrics.append(metrics)
    st.rerun()


def _tool_call_card(event: dict, index: int) -> None:
    tool_name = event["name"]
    icon = _TOOL_ICONS.get(tool_name, "🔩")
    args_pretty = json.dumps(event["args"], indent=2)
    args_html = html.escape(args_pretty)

    st.html(f"""
    <div style="
        margin: 5px 0;
        border-left: 3px solid #6C63FF;
        background: rgba(108,99,255,0.07);
        border-radius: 0 8px 8px 0;
        padding: 10px 14px;
        font-family: system-ui, sans-serif;
    ">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span style="
                background: #6C63FF;
                color: white;
                border-radius: 50%;
                width: 22px; height: 22px;
                display: inline-flex; align-items: center; justify-content: center;
                font-size: 11px; font-weight: 700; flex-shrink: 0;
            ">{index}</span>
            <span style="font-size: 16px;">{icon}</span>
            <code style="
                background: rgba(108,99,255,0.25);
                color: #b0abff;
                border-radius: 5px;
                padding: 2px 10px;
                font-size: 13px; font-weight: 600;
            ">{html.escape(tool_name)}</code>
            <span style="color: rgba(255,255,255,0.3); font-size: 11px; margin-left: auto;">tool call</span>
        </div>
        <pre style="
            background: rgba(0,0,0,0.35);
            border-radius: 6px; padding: 10px;
            font-size: 11px; color: #a0a8c0;
            overflow-x: auto; margin: 0;
            white-space: pre-wrap; word-break: break-all;
            max-height: 200px;
        ">{args_html}</pre>
    </div>
    """)


def _tool_result_card(event: dict, index: int) -> None:
    result = event["result"]
    result_str = json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
    result_html = html.escape(result_str)
    # Truncate long results for display
    lines = result_str.splitlines()
    truncated = len(lines) > 30
    display_html = html.escape("\n".join(lines[:30]) + ("\n…(truncated)" if truncated else ""))

    st.html(f"""
    <div style="
        margin: 3px 0 10px 28px;
        border-left: 3px solid #238636;
        background: rgba(35,134,54,0.07);
        border-radius: 0 8px 8px 0;
        padding: 8px 14px;
        font-family: system-ui, sans-serif;
    ">
        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
            <span style="color: #3fb950; font-size: 12px; font-weight: 600;">✓ result</span>
            <span style="color: rgba(255,255,255,0.3); font-size: 11px;">step {index}</span>
        </div>
        <pre style="
            background: rgba(0,0,0,0.3);
            border-radius: 6px; padding: 8px;
            font-size: 11px; color: #8b949e;
            overflow-x: auto; margin: 0;
            white-space: pre-wrap; word-break: break-all;
            max-height: 160px;
        ">{display_html}</pre>
    </div>
    """)


def _metrics_badge(metrics: dict, ctx: ConversationContext | None = None) -> None:
    tool_count = metrics.get("tool_call_count", 0)
    latency = metrics.get("latency_ms", 0)
    tokens = metrics.get("tokens", 0)
    ctx_est = f" &nbsp;·&nbsp; ctx≈{ctx.token_estimate} tok" if ctx else ""

    st.html(f"""
    <div style="
        display: inline-flex; align-items: center; gap: 10px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px; padding: 3px 12px;
        font-size: 11px; color: rgba(255,255,255,0.45);
        font-family: system-ui, sans-serif;
        margin-top: 6px;
    ">
        <span>🔩 {tool_count} tools</span>
        <span style="opacity:0.4">·</span>
        <span>⏱ {latency}ms</span>
        <span style="opacity:0.4">·</span>
        <span>🪙 {tokens} tok{ctx_est}</span>
    </div>
    """)


def render_chat_tab() -> None:
    _subscribe_approval_events()

    if "context" not in st.session_state:
        st.session_state.context = ConversationContext()
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "turn_metrics" not in st.session_state:
        st.session_state.turn_metrics = []

    ctx: ConversationContext = st.session_state.context

    # Render history
    for entry in st.session_state.chat_messages:
        if entry["content"] in ("__approval_confirmed__", "__approval_cancelled__"):
            continue
        with st.chat_message(entry["role"]):
            if entry["role"] == "user":
                st.markdown(entry["content"])
            else:
                _render_assistant_entry(entry)

    _render_approval_cards()
    _maybe_process_approval(ctx)

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
                _metrics_badge(metrics, ctx)

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
        _metrics_badge(m)
