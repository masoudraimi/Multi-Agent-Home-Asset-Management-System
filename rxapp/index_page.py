"""Main application page with Chat, Assets, Schedule and Admin tabs."""

import reflex as rx
from rxapp.state import State, ToolCall, Message, Approval, UserRow

# ── Colour constants ────────────────────────────────────────────────────────────
_VIOLET = "violet"
_GREY = "gray"

CATEGORIES = ["All", "appliances", "HVAC", "plumbing", "electrical",
               "exterior", "vehicle", "garden", "plants_trees", "other"]


# ── Chat tab ───────────────────────────────────────────────────────────────────

def _tool_call_item(tc: ToolCall) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.badge(tc.step, color_scheme=_VIOLET, variant="solid", size="1"),
            rx.text(tc.icon, size="2"),
            rx.code(tc.name, size="1"),
            rx.spacer(),
            rx.text("tool call", size="1", color_scheme=_GREY),
            align="center",
            width="100%",
        ),
        rx.code_block(
            tc.args_str,
            language="json",
            font_size="11px",
            can_copy=False,
        ),
        rx.cond(
            tc.result_str != "",
            rx.box(
                rx.hstack(
                    rx.icon("check", size=12, color="green"),
                    rx.text("result", size="1", color_scheme="green"),
                ),
                rx.code_block(
                    tc.result_str,
                    language="json",
                    font_size="11px",
                    can_copy=False,
                ),
                padding_left="1em",
                border_left="2px solid var(--green-9)",
                margin_top="4px",
            ),
            rx.fragment(),
        ),
        border_left="3px solid var(--violet-9)",
        padding="10px 14px",
        margin_y="4px",
        border_radius="0 8px 8px 0",
        background="color-mix(in srgb, var(--violet-9) 7%, transparent)",
    )


def _assistant_bubble(msg: Message) -> rx.Component:
    return rx.vstack(
        rx.cond(
            msg.has_tools,
            rx.vstack(
                rx.foreach(msg.tool_calls, _tool_call_item),
                spacing="1",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.markdown(
            msg.content,
            component_map={
                "p": lambda text: rx.text(text, size="2"),
                "code": lambda text: rx.code(text, size="1"),
            },
        ),
        align="start",
        width="100%",
        spacing="2",
    )


def _chat_message(msg: Message) -> rx.Component:
    return rx.cond(
        msg.role == "user",
        rx.hstack(
            rx.spacer(),
            rx.box(
                rx.text(msg.content, size="2"),
                background="color-mix(in srgb, var(--violet-9) 15%, transparent)",
                border="1px solid var(--violet-6)",
                border_radius="12px 12px 2px 12px",
                padding="10px 14px",
                max_width="75%",
            ),
            width="100%",
        ),
        rx.hstack(
            rx.avatar(fallback="AI", size="2", color_scheme=_VIOLET, variant="soft"),
            rx.box(
                _assistant_bubble(msg),
                background="color-mix(in srgb, var(--gray-3) 60%, transparent)",
                border="1px solid var(--gray-6)",
                border_radius="2px 12px 12px 12px",
                padding="12px 16px",
                flex="1",
            ),
            align="start",
            width="100%",
        ),
    )


def _approval_card(approval: Approval) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("triangle-alert", size=16, color="orange"),
                rx.text("Action requires your approval", weight="bold", size="2"),
                align="center",
                spacing="2",
            ),
            rx.hstack(
                rx.badge(approval.agent_name, color_scheme="orange", size="1"),
                rx.text(approval.request_id, size="1", color_scheme=_GREY),
                spacing="2",
            ),
            rx.text(approval.action_description, size="2"),
            rx.code_block(
                approval.payload_str,
                language="json",
                font_size="11px",
                can_copy=False,
            ),
            rx.hstack(
                rx.button(
                    rx.icon("check", size=14),
                    "Confirm",
                    color_scheme="green",
                    size="2",
                    on_click=State.confirm_approval(approval.request_id),
                ),
                rx.button(
                    rx.icon("x", size=14),
                    "Cancel",
                    color_scheme="red",
                    variant="soft",
                    size="2",
                    on_click=State.cancel_approval(approval.request_id),
                ),
                spacing="3",
            ),
            spacing="3",
            align="start",
        ),
        border="1px solid var(--orange-7)",
        background="color-mix(in srgb, var(--orange-9) 8%, transparent)",
    )


def chat_tab() -> rx.Component:
    return rx.vstack(
        rx.scroll_area(
            rx.vstack(
                rx.foreach(State.messages, _chat_message),
                rx.cond(
                    State.is_thinking,
                    rx.hstack(
                        rx.avatar(fallback="AI", size="2", color_scheme=_VIOLET, variant="soft"),
                        rx.box(
                            rx.hstack(
                                rx.spinner(size="2"),
                                rx.text("Thinking…", size="2", color_scheme=_GREY),
                                spacing="2",
                                align="center",
                            ),
                            padding="12px 16px",
                        ),
                        align="center",
                        spacing="3",
                    ),
                    rx.fragment(),
                ),
                spacing="3",
                padding="16px",
                width="100%",
            ),
            type="hover",
            scrollbars="vertical",
            height="calc(100vh - 280px)",
            width="100%",
        ),
        rx.cond(
            State.has_pending_approvals,
            rx.vstack(
                rx.foreach(State.pending_approvals, _approval_card),
                spacing="2",
                width="100%",
                padding_x="16px",
            ),
            rx.fragment(),
        ),
        rx.form(
            rx.hstack(
                rx.input(
                    placeholder="Ask about your home assets…",
                    name="prompt",
                    size="3",
                    flex="1",
                    disabled=State.is_thinking,
                ),
                rx.button(
                    rx.icon("send", size=16),
                    type="submit",
                    size="3",
                    color_scheme=_VIOLET,
                    disabled=State.is_thinking,
                ),
                spacing="2",
                width="100%",
            ),
            on_submit=State.send_message,
            reset_on_submit=True,
            width="100%",
            padding="12px 16px",
        ),
        spacing="0",
        width="100%",
        height="100%",
    )


# ── Assets tab ─────────────────────────────────────────────────────────────────

def _asset_row(asset: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(asset["id"]),
        rx.table.cell(rx.text(asset["name"], weight="medium")),
        rx.table.cell(
            rx.badge(asset["category"], color_scheme=_VIOLET, variant="soft", size="1")
        ),
        rx.table.cell(asset["brand"]),
        rx.table.cell(asset["location"]),
        rx.table.cell(asset["purchase_date"]),
        rx.table.cell(asset["warranty_expiry"]),
        on_click=State.select_asset(asset["name"]),
        cursor="pointer",
        _hover={"background": "color-mix(in srgb, var(--violet-9) 6%, transparent)"},
    )


def _asset_detail() -> rx.Component:
    return rx.cond(
        State.has_selected_asset,
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.text(
                        State.selected_asset["name"],
                        weight="bold",
                        size="4",
                    ),
                    rx.spacer(),
                    rx.badge(
                        State.selected_asset["category"],
                        color_scheme=_VIOLET,
                        size="2",
                    ),
                    align="center",
                    width="100%",
                ),
                rx.separator(size="4"),
                rx.grid(
                    rx.vstack(
                        rx.text("Brand", size="1", color_scheme=_GREY, weight="bold"),
                        rx.text(State.selected_asset["brand"], size="2"),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Model", size="1", color_scheme=_GREY, weight="bold"),
                        rx.text(State.selected_asset["model"], size="2"),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Location", size="1", color_scheme=_GREY, weight="bold"),
                        rx.text(State.selected_asset["location"], size="2"),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Purchased", size="1", color_scheme=_GREY, weight="bold"),
                        rx.text(State.selected_asset["purchase_date"], size="2"),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Price", size="1", color_scheme=_GREY, weight="bold"),
                        rx.text(State.selected_asset["purchase_price"], size="2"),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Warranty", size="1", color_scheme=_GREY, weight="bold"),
                        rx.text(State.selected_asset["warranty_expiry"], size="2"),
                        spacing="1",
                    ),
                    columns="3",
                    spacing="4",
                    width="100%",
                ),
                rx.cond(
                    State.selected_asset["notes"] != "",
                    rx.box(
                        rx.text(State.selected_asset["notes"], size="2"),
                        border_left="3px solid var(--violet-9)",
                        padding_left="12px",
                        color_scheme=_GREY,
                    ),
                    rx.fragment(),
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
        ),
        rx.callout(
            "Select an asset from the table to view its details.",
            icon="info",
            color_scheme=_GREY,
        ),
    )


def assets_tab() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading("Asset Inventory", size="5"),
            rx.spacer(),
            rx.card(
                rx.vstack(
                    rx.text(State.asset_count, size="6", weight="bold", color_scheme=_VIOLET),
                    rx.text("assets", size="1", color_scheme=_GREY),
                    spacing="0",
                    align="center",
                ),
                padding="12px 20px",
            ),
            align="center",
            width="100%",
        ),
        rx.select(
            CATEGORIES,
            value=State.asset_category,
            on_change=State.set_asset_category,
            size="2",
            width="220px",
        ),
        rx.cond(
            State.asset_count == 0,
            rx.callout("No assets found. Ask the chat agent to add some!", icon="package-open", color_scheme=_GREY),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("ID"),
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Category"),
                        rx.table.column_header_cell("Brand"),
                        rx.table.column_header_cell("Location"),
                        rx.table.column_header_cell("Purchased"),
                        rx.table.column_header_cell("Warranty"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(State.display_assets, _asset_row),
                ),
                width="100%",
                size="1",
            ),
        ),
        rx.separator(size="4"),
        rx.heading("Asset Details", size="4"),
        _asset_detail(),
        spacing="4",
        align="start",
        width="100%",
        padding="16px",
    )


# ── Schedule tab ───────────────────────────────────────────────────────────────

def _task_card(task: dict) -> rx.Component:
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.text(task["asset_name"], weight="bold", size="2"),
                    rx.text("—", size="2", color_scheme=_GREY),
                    rx.text(task["task_name"], size="2"),
                    spacing="2",
                    flex_wrap="wrap",
                ),
                rx.hstack(
                    rx.badge(task["category"], size="1", variant="soft", color_scheme=_GREY),
                    rx.text(task["completed_date"], size="1", color_scheme=_GREY),
                    spacing="2",
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rx.vstack(
                rx.badge(
                    task["urgency"],
                    color_scheme=rx.cond(
                        task["urgency"] == "overdue", "red",
                        rx.cond(task["urgency"] == "due_soon", "orange", "green")
                    ),
                    variant="solid",
                    size="1",
                ),
                rx.text(task["due_label"], size="1", color_scheme=_GREY),
                spacing="1",
                align="end",
            ),
            align="center",
            width="100%",
        ),
        border_left=rx.cond(
            task["urgency"] == "overdue", "4px solid var(--red-9)",
            rx.cond(task["urgency"] == "due_soon", "4px solid var(--orange-9)", "4px solid var(--green-9)")
        ),
    )


def schedule_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("Maintenance Schedule", size="5"),
        rx.hstack(
            rx.text("Show tasks due within:", size="2"),
            rx.slider(
                min=7,
                max=365,
                value=[State.schedule_days],
                on_value_commit=State.set_schedule_days,
                width="240px",
            ),
            rx.text(State.schedule_days, " days", size="2", color_scheme=_VIOLET),
            rx.button(
                "Refresh",
                on_click=State.load_schedule,
                size="2",
                variant="soft",
                color_scheme=_VIOLET,
            ),
            spacing="4",
            align="center",
            flex_wrap="wrap",
        ),
        rx.grid(
            rx.card(
                rx.vstack(
                    rx.text(State.overdue_count, size="7", weight="bold", color="var(--red-9)"),
                    rx.text("Overdue", size="1", color_scheme=_GREY, weight="bold"),
                    align="center", spacing="1",
                ),
                background="color-mix(in srgb, var(--red-9) 8%, transparent)",
                border="1px solid var(--red-6)",
            ),
            rx.card(
                rx.vstack(
                    rx.text(State.due_soon_count, size="7", weight="bold", color="var(--orange-9)"),
                    rx.text("Due this week", size="1", color_scheme=_GREY, weight="bold"),
                    align="center", spacing="1",
                ),
                background="color-mix(in srgb, var(--orange-9) 8%, transparent)",
                border="1px solid var(--orange-6)",
            ),
            rx.card(
                rx.vstack(
                    rx.text(State.upcoming_count, size="7", weight="bold", color="var(--green-9)"),
                    rx.text("Upcoming", size="1", color_scheme=_GREY, weight="bold"),
                    align="center", spacing="1",
                ),
                background="color-mix(in srgb, var(--green-9) 8%, transparent)",
                border="1px solid var(--green-6)",
            ),
            columns="3",
            spacing="3",
            width="100%",
        ),
        rx.cond(
            State.upcoming_count + State.overdue_count + State.due_soon_count == 0,
            rx.callout("No maintenance tasks due in this period.", icon="circle-check", color_scheme="green"),
            rx.vstack(
                rx.foreach(State.tasks, _task_card),
                spacing="2",
                width="100%",
            ),
        ),
        spacing="4",
        align="start",
        width="100%",
        padding="16px",
    )


# ── Admin tab ──────────────────────────────────────────────────────────────────

def _user_row(user: UserRow) -> rx.Component:
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.text(user.email, weight="medium", size="2"),
                rx.hstack(
                    rx.badge(
                        user.role,
                        color_scheme=rx.cond(user.role == "admin", _VIOLET, _GREY),
                        size="1",
                    ),
                    rx.badge(
                        rx.cond(user.is_active, "active", "inactive"),
                        color_scheme=rx.cond(user.is_active, "green", "red"),
                        size="1",
                        variant="soft",
                    ),
                    spacing="2",
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rx.hstack(
                rx.button(
                    rx.cond(user.role == "admin", "Make user", "Make admin"),
                    on_click=State.toggle_user_role(user.id, user.role),
                    size="1",
                    variant="soft",
                    color_scheme=_VIOLET,
                ),
                rx.button(
                    rx.cond(user.is_active, "Deactivate", "Activate"),
                    on_click=State.toggle_user_active(user.id, user.is_active),
                    size="1",
                    variant="soft",
                    color_scheme=rx.cond(user.is_active, "red", "green"),
                ),
                spacing="2",
            ),
            align="center",
            width="100%",
        ),
    )


def admin_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("User Management", size="5"),
        rx.cond(
            State.admin_error != "",
            rx.callout(State.admin_error, color="red", icon="circle-x"),
            rx.fragment(),
        ),
        rx.cond(
            State.admin_success != "",
            rx.callout(State.admin_success, color="green", icon="circle-check"),
            rx.fragment(),
        ),
        rx.card(
            rx.vstack(
                rx.text("Create new user", weight="bold", size="3"),
                rx.form(
                    rx.vstack(
                        rx.hstack(
                            rx.input(
                                placeholder="Email",
                                name="email",
                                type="email",
                                size="2",
                                flex="1",
                            ),
                            rx.input(
                                placeholder="Temporary password",
                                name="password",
                                type="password",
                                size="2",
                                flex="1",
                            ),
                            rx.select(
                                ["user", "admin"],
                                name="role",
                                default_value="user",
                                size="2",
                            ),
                            rx.button(
                                "Create",
                                type="submit",
                                size="2",
                                color_scheme=_VIOLET,
                            ),
                            spacing="2",
                            flex_wrap="wrap",
                            width="100%",
                        ),
                        width="100%",
                    ),
                    on_submit=State.create_user,
                    reset_on_submit=True,
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
        ),
        rx.vstack(
            rx.foreach(State.admin_users, _user_row),
            spacing="2",
            width="100%",
        ),
        spacing="4",
        align="start",
        width="100%",
        padding="16px",
        on_mount=State.load_admin_users,
    )


# ── Sidebar ────────────────────────────────────────────────────────────────────

def sidebar() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text("🏠", font_size="1.6em"),
                rx.vstack(
                    rx.text("Home Asset Agent", weight="bold", size="3"),
                    rx.text("AI-powered maintenance", size="1", color_scheme=_GREY),
                    spacing="0",
                ),
                spacing="3",
                align="center",
            ),
            rx.separator(size="4"),
            rx.vstack(
                rx.hstack(
                    rx.avatar(
                        fallback=State.user_email[:2].upper(),
                        size="2",
                        color_scheme=_VIOLET,
                    ),
                    rx.vstack(
                        rx.text(State.user_email, size="2", weight="medium"),
                        rx.badge(State.user_role, size="1", variant="soft", color_scheme=_GREY),
                        spacing="0",
                        align="start",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.button(
                    "Log out",
                    on_click=State.logout,
                    size="2",
                    width="100%",
                    variant="soft",
                    color_scheme=_GREY,
                ),
                spacing="3",
                width="100%",
            ),
            rx.separator(size="4"),
            rx.callout(
                "Agent ready",
                icon="circle-check",
                color_scheme="green",
                size="1",
            ),
            rx.separator(size="4"),
            rx.vstack(
                rx.text("Example queries", size="1", weight="bold", color_scheme=_GREY),
                *[
                    rx.text(f"· {q}", size="1", color_scheme=_GREY)
                    for q in [
                        "What maintenance is due?",
                        "When does my dishwasher warranty expire?",
                        "How much have I spent on the car?",
                        "I want to add a new dishwasher",
                        "What plants do I have?",
                        "What home assets am I missing?",
                    ]
                ],
                spacing="1",
                align="start",
            ),
            rx.separator(size="4"),
            rx.button(
                rx.icon("rotate-ccw", size=14),
                "Clear chat",
                on_click=State.clear_chat,
                size="2",
                width="100%",
                variant="ghost",
                color_scheme=_GREY,
            ),
            spacing="4",
            align="start",
            width="100%",
            padding="16px",
        ),
        width="240px",
        min_height="100vh",
        border_right="1px solid var(--gray-6)",
        background="var(--gray-2)",
        flex_shrink="0",
    )


# ── Main page ──────────────────────────────────────────────────────────────────

def index_page() -> rx.Component:
    return rx.cond(
        State.is_authenticated,
        rx.hstack(
            sidebar(),
            rx.box(
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("💬 Chat", value="chat"),
                        rx.tabs.trigger(
                            "📦 Assets",
                            value="assets",
                            on_click=State.load_assets,
                        ),
                        rx.tabs.trigger(
                            "🗓 Schedule",
                            value="schedule",
                            on_click=State.load_schedule,
                        ),
                        rx.cond(
                            State.is_admin,
                            rx.tabs.trigger(
                                "👤 Admin",
                                value="admin",
                                on_click=State.load_admin_users,
                            ),
                            rx.fragment(),
                        ),
                        size="2",
                    ),
                    rx.tabs.content(chat_tab(), value="chat"),
                    rx.tabs.content(assets_tab(), value="assets"),
                    rx.tabs.content(schedule_tab(), value="schedule"),
                    rx.cond(
                        State.is_admin,
                        rx.tabs.content(admin_tab(), value="admin"),
                        rx.fragment(),
                    ),
                    default_value="chat",
                    width="100%",
                ),
                flex="1",
                overflow="hidden",
            ),
            spacing="0",
            align="start",
            min_height="100vh",
            width="100%",
        ),
        rx.center(
            rx.vstack(
                rx.spinner(size="3"),
                rx.text("Redirecting to login…", color_scheme=_GREY),
                spacing="3",
                align="center",
            ),
            min_height="100vh",
        ),
    )
