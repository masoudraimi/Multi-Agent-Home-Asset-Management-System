"""Single Reflex state for the entire WiseWombat app.

All state lives here to avoid sub-state complexity. The ContextVar
(core/session.py) is re-applied at the start of every event handler that
touches the database so that user-scoped queries work correctly inside
Reflex's async event loop.
"""

from __future__ import annotations

import asyncio
import json

import dataclasses
import reflex as rx

from rxapp.sessions import clear_context, get_context

# ── Tool emoji map ─────────────────────────────────────────────────────────────
_TOOL_ICONS: dict[str, str] = {
    "add_asset": "📦", "list_assets": "📋", "search_assets": "🔍",
    "update_asset": "✏️", "log_maintenance": "🔧",
    "get_upcoming_maintenance": "🗓", "get_asset_history": "📜",
    "get_onboarding_questions": "❓", "review_asset_draft": "🔎",
    "get_plant_care_schedule": "🌿", "suggest_missing_assets": "💡",
    "get_expiring_warranties": "⚠️",
}

_CAT_ICONS: dict[str, str] = {
    "appliances": "🏠", "HVAC": "❄️", "plumbing": "🚿", "electrical": "⚡",
    "exterior": "🏡", "vehicle": "🚗", "garden": "🌱",
    "plants_trees": "🌳", "other": "📦",
}


def _set_user(user_id: str) -> None:
    """Apply the user ContextVar for this async task."""
    from core.session import set_current_user
    set_current_user(user_id)


def _langgraph_owns_approvals() -> bool:
    """True when any specialist that can raise an approval runs on the graph."""
    from agents.orchestrator.agent import _use_langgraph
    # Asset is the only specialist that publishes HumanApprovalRequested today.
    return _use_langgraph("asset")


def _build_from_events(raw_events: list[dict]) -> tuple[list["ToolCall"], str, list["Approval"]]:
    """Fold a list of adapter/runner events into UI-facing objects.

    Returns (tool_calls, final_answer_text, new_approvals). tool_calls are
    numbered starting at 1. Missing tool_result entries are left with empty
    result_str. Very long results are truncated at 25 lines.
    """
    tool_calls: list[ToolCall] = []
    answer = ""
    step = 0
    pending_calls: dict[str, ToolCall] = {}
    new_approvals: list[Approval] = []

    for ev in raw_events:
        t = ev.get("type")
        if t == "tool_call":
            step += 1
            tc = ToolCall(
                step=step,
                name=ev["name"],
                icon=_TOOL_ICONS.get(ev["name"], "🔩"),
                args_str=json.dumps(ev.get("args", {}), indent=2),
                result_str="",
            )
            tool_calls.append(tc)
            pending_calls[ev["call_id"]] = tc
        elif t == "tool_result":
            tc = pending_calls.get(ev.get("call_id", ""))
            if tc:
                result = ev.get("result", "")
                if isinstance(result, (dict, list)):
                    result = json.dumps(result, indent=2)
                lines = str(result).splitlines()
                if len(lines) > 25:
                    result = "\n".join(lines[:25]) + "\n…(truncated)"
                tc.result_str = str(result)
        elif t == "assistant_text":
            answer = ev.get("content", "")
        elif t == "pending_approval":
            new_approvals.append(Approval(
                request_id=ev.get("request_id", ""),
                agent_name=ev.get("agent_name", ""),
                action_description=ev.get("action_description", ""),
                payload_str=ev.get("payload_str", ""),
                thread_id=ev.get("thread_id", ""),
            ))

    return tool_calls, answer, new_approvals


async def _resolve_approval(
    approval: "Approval | None",
    ctx,
    *,
    approved: bool,
) -> list[dict]:
    """Route confirm/cancel of a pending approval to the right backend.

    Graph-based approvals carry a thread_id and resume via LangGraph's
    Command(resume=...). Legacy BaseAgent approvals fall back to the
    __approval_confirmed__ / __approval_cancelled__ sentinel path.
    """
    if approval is not None and approval.thread_id:
        from agent.langgraph_adapter import resume_graph_turn
        from agents.asset.graph import GRAPH
        return await resume_graph_turn(
            GRAPH,
            thread_id=approval.thread_id,
            approved=approved,
            context=ctx,
            agent_name=approval.agent_name or "asset",
        )
    # Legacy path
    from agent.runner import run_turn_in_loop
    sentinel = "__approval_confirmed__" if approved else "__approval_cancelled__"
    return await run_turn_in_loop(sentinel, ctx)


# ── Typed data models ─────────────────────────────────────────────────────────

@dataclasses.dataclass
class ToolCall:
    step: int = 0
    name: str = ""
    icon: str = ""
    args_str: str = ""
    result_str: str = ""


@dataclasses.dataclass
class Message:
    role: str = ""
    content: str = ""
    has_tools: bool = False
    tool_calls: list[ToolCall] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Approval:
    request_id: str = ""
    agent_name: str = ""
    action_description: str = ""
    payload_str: str = ""
    thread_id: str = ""     # populated when the approval comes from a LangGraph interrupt


@dataclasses.dataclass
class UserRow:
    id: str = ""
    email: str = ""
    role: str = "user"
    is_active: bool = True
    created_at: str = ""


class State(rx.State):
    # ── Auth ───────────────────────────────────────────────────────────────────
    user_id: str = ""
    user_email: str = ""
    user_role: str = ""
    is_authenticated: bool = False
    login_error: str = ""
    active_tab: str = "chat"

    # ── Chat ───────────────────────────────────────────────────────────────────
    messages: list[Message] = []
    is_thinking: bool = False
    pending_approvals: list[Approval] = []
    session_id: str = ""     # stable per Reflex session; drives LangGraph thread_id

    # ── Assets ─────────────────────────────────────────────────────────────────
    assets: list[dict] = []
    asset_count: int = 0
    asset_category: str = "All"
    selected_asset: dict = {}
    has_selected_asset: bool = False

    # ── Schedule ───────────────────────────────────────────────────────────────
    tasks: list[dict] = []
    schedule_days: int = 60
    overdue_count: int = 0
    due_soon_count: int = 0
    upcoming_count: int = 0

    # ── Admin ──────────────────────────────────────────────────────────────────
    admin_users: list[UserRow] = []
    admin_error: str = ""
    admin_success: str = ""

    # ── Computed vars ──────────────────────────────────────────────────────────
    @rx.var
    def is_admin(self) -> bool:
        return self.user_role == "admin"

    @rx.var
    def has_pending_approvals(self) -> bool:
        return len(self.pending_approvals) > 0

    @rx.var
    def display_assets(self) -> list[dict]:
        if self.asset_category == "All":
            return self.assets
        return [a for a in self.assets if a.get("category") == self.asset_category]

    # ── Auth event handlers ────────────────────────────────────────────────────
    @rx.event
    async def login(self, form_data: dict):
        from core.auth import authenticate
        email = form_data.get("email", "").strip()
        password = form_data.get("password", "")
        if not email or not password:
            self.login_error = "Please enter your email and password."
            return
        try:
            user = authenticate(email, password)
        except Exception as exc:
            self.login_error = f"Connection error: {exc}"
            return
        if user and user.get("is_active", True):
            self.user_id = str(user["id"])
            self.user_email = user["email"]
            self.user_role = user.get("role", "user")
            self.is_authenticated = True
            self.login_error = ""
            yield rx.redirect("/")
        else:
            self.login_error = "Invalid email or password, or your account is inactive."

    @rx.event
    async def logout(self):
        clear_context(self.user_id)
        self.user_id = ""
        self.user_email = ""
        self.user_role = ""
        self.is_authenticated = False
        self.messages = []
        self.assets = []
        self.tasks = []
        self.pending_approvals = []
        yield rx.redirect("/login")

    @rx.event
    async def require_auth(self):
        if not self.is_authenticated:
            yield rx.redirect("/login")

    @rx.event
    def set_active_tab(self, tab: str):
        self.active_tab = tab

    # ── Chat event handlers ────────────────────────────────────────────────────
    @rx.event
    async def send_message(self, form_data: dict):
        prompt = form_data.get("prompt", "").strip()
        if not prompt or not self.is_authenticated or self.is_thinking:
            return

        self.messages = [
            *self.messages,
            Message(role="user", content=prompt, has_tools=False, tool_calls=[]),
        ]
        self.is_thinking = True
        yield

        _set_user(self.user_id)
        if not self.session_id:
            import uuid
            self.session_id = uuid.uuid4().hex[:16]
        thread_id = f"{self.user_id}:{self.session_id}"
        ctx = get_context(self.user_id)

        # Only subscribe to the EventBus approval channel when the BaseAgent
        # path is active for asset (the graph uses interrupt() instead).
        eventbus_active = not _langgraph_owns_approvals()
        approval_queue: asyncio.Queue | None = None
        bus = None
        if eventbus_active:
            from core.event_bus import EventBus
            from core.events import HumanApprovalRequested
            approval_queue = asyncio.Queue()
            bus = EventBus()
            bus.subscribe_async(HumanApprovalRequested, approval_queue)

        try:
            from agent.runner import run_turn_in_loop
            raw_events = await run_turn_in_loop(prompt, ctx, thread_id=thread_id)
        finally:
            if bus and approval_queue is not None:
                try:
                    from core.events import HumanApprovalRequested
                    bus._async_queues[HumanApprovalRequested].remove(approval_queue)
                except (ValueError, KeyError):
                    pass

        tool_calls, answer, new_approvals = _build_from_events(raw_events)

        # Merge EventBus-published approvals (BaseAgent path)
        if approval_queue is not None:
            while not approval_queue.empty():
                ap = approval_queue.get_nowait()
                new_approvals.append(Approval(
                    request_id=ap.request_id,
                    agent_name=ap.agent_name,
                    action_description=ap.action_description,
                    payload_str=json.dumps(ap.payload, indent=2),
                    thread_id="",     # empty ⇒ resume via old sentinel path
                ))

        if answer:
            self.messages = [
                *self.messages,
                Message(
                    role="assistant",
                    content=answer,
                    has_tools=len(tool_calls) > 0,
                    tool_calls=tool_calls,
                ),
            ]

        if new_approvals:
            self.pending_approvals = [*self.pending_approvals, *new_approvals]

        self.is_thinking = False

    @rx.event
    async def confirm_approval(self, request_id: str):
        approval = next((a for a in self.pending_approvals if a.request_id == request_id), None)
        self.pending_approvals = [a for a in self.pending_approvals if a.request_id != request_id]
        self.is_thinking = True
        yield

        _set_user(self.user_id)
        ctx = get_context(self.user_id)

        raw_events = await _resolve_approval(approval, ctx, approved=True)
        tool_calls, answer, more_approvals = _build_from_events(raw_events)

        if answer:
            self.messages = [
                *self.messages,
                Message(
                    role="assistant",
                    content=answer,
                    has_tools=len(tool_calls) > 0,
                    tool_calls=tool_calls,
                ),
            ]
        if more_approvals:
            self.pending_approvals = [*self.pending_approvals, *more_approvals]
        self.is_thinking = False

    @rx.event
    async def cancel_approval(self, request_id: str):
        approval = next((a for a in self.pending_approvals if a.request_id == request_id), None)
        self.pending_approvals = [a for a in self.pending_approvals if a.request_id != request_id]

        # Legacy BaseAgent approvals (no thread_id): just drop, no follow-up call.
        if approval is None or not approval.thread_id:
            return

        self.is_thinking = True
        yield

        _set_user(self.user_id)
        ctx = get_context(self.user_id)
        raw_events = await _resolve_approval(approval, ctx, approved=False)
        tool_calls, answer, _ = _build_from_events(raw_events)

        if answer:
            self.messages = [
                *self.messages,
                Message(
                    role="assistant",
                    content=answer,
                    has_tools=len(tool_calls) > 0,
                    tool_calls=tool_calls,
                ),
            ]
        self.is_thinking = False

    @rx.event
    def clear_chat(self):
        self.messages = []
        self.pending_approvals = []
        clear_context(self.user_id)

    # ── Assets event handlers ──────────────────────────────────────────────────
    @rx.event
    def load_assets(self):
        _set_user(self.user_id)
        from db import get_provider
        result = get_provider().list_assets(self.user_id)
        self.asset_count = result.get("count", 0)
        rows = result.get("assets", [])
        self.assets = [_clean_row(r) for r in rows]
        self.selected_asset = {}
        self.has_selected_asset = False

    @rx.event
    def set_asset_category(self, category: str):
        self.asset_category = category

    @rx.event
    def select_asset(self, name: str):
        for a in self.assets:
            if a.get("name") == name:
                self.selected_asset = a
                self.has_selected_asset = True
                return
        self.selected_asset = {}
        self.has_selected_asset = False

    # ── Schedule event handlers ────────────────────────────────────────────────
    @rx.event
    def load_schedule(self):
        _set_user(self.user_id)
        from db import get_provider
        result = get_provider().get_upcoming_maintenance(self.user_id, self.schedule_days)
        raw = result.get("tasks", [])
        tasks = []
        overdue = due_soon = upcoming = 0
        for t in raw:
            urgency = t.get("urgency", "upcoming")
            if urgency == "overdue":
                overdue += 1
            elif urgency == "due_soon":
                due_soon += 1
            else:
                upcoming += 1
            days = t.get("days_until_due", 0)
            if days < 0:
                due_label = f"{abs(int(days))}d overdue"
            elif days == 0:
                due_label = "Due today"
            else:
                due_label = f"in {int(days)}d"
            tasks.append({
                "asset_name": str(t.get("asset_name", "")),
                "task_name": str(t.get("task_name", "")),
                "category": str(t.get("category", "")),
                "urgency": urgency,
                "due_label": due_label,
                "completed_date": str(t.get("completed_date") or "Never serviced"),
            })
        self.tasks = sorted(tasks, key=lambda x: {"overdue": 0, "due_soon": 1, "upcoming": 2}.get(x["urgency"], 3))
        self.overdue_count = overdue
        self.due_soon_count = due_soon
        self.upcoming_count = upcoming

    @rx.event
    def set_schedule_days(self, days: list[float]):
        if days:
            self.schedule_days = int(days[0])

    # ── Admin event handlers ───────────────────────────────────────────────────
    @rx.event
    def load_admin_users(self):
        if not self.is_admin:
            return
        from core import auth
        users = auth.list_users()
        self.admin_users = [
            UserRow(
                id=str(u["id"]),
                email=str(u["email"]),
                role=str(u.get("role", "user")),
                is_active=bool(u.get("is_active", True)),
                created_at=str(u.get("created_at", "")),
            )
            for u in users
        ]

    @rx.event
    def create_user(self, form_data: dict):
        if not self.is_admin:
            return
        email = form_data.get("email", "").strip()
        password = form_data.get("password", "")
        role = form_data.get("role", "user")
        try:
            from core import auth
            auth.create_user(email, password, role)
            self.admin_success = f"User {email} created."
            self.admin_error = ""
            return State.load_admin_users
        except Exception as e:
            self.admin_error = str(e)
            self.admin_success = ""

    @rx.event
    def toggle_user_active(self, user_id: str, is_active: bool):
        if not self.is_admin:
            return
        try:
            from core import auth
            auth.set_active(user_id, not is_active)
            return State.load_admin_users
        except Exception as e:
            self.admin_error = str(e)

    @rx.event
    def toggle_user_role(self, user_id: str, current_role: str):
        if not self.is_admin:
            return
        new_role = "user" if current_role == "admin" else "admin"
        try:
            from core import auth
            auth.set_role(user_id, new_role)
            return State.load_admin_users
        except Exception as e:
            self.admin_error = str(e)


def _clean_row(row: dict) -> dict:
    """Normalise a DB row: convert None/NaN to empty string for Reflex serialisation."""
    import math
    out = {}
    for k, v in row.items():
        if v is None:
            out[k] = ""
        elif isinstance(v, float) and math.isnan(v):
            out[k] = ""
        else:
            out[k] = str(v) if not isinstance(v, (int, float, bool)) else v
    return out
