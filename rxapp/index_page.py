"""Main application page - enterprise admin panel layout."""

import reflex as rx
from rxapp.state import State, ToolCall, Message, Approval, UserRow
from rxapp import styles

CATEGORIES = ["All", "appliances", "HVAC", "plumbing", "electrical",
               "exterior", "vehicle", "garden", "plants_trees", "other"]


# ── Sidebar navigation ─────────────────────────────────────────────────────────

def _nav_item(label: str, icon_name: str, tab_value: str,
              extra_handler=None) -> rx.Component:
    is_active = State.active_tab == tab_value
    handlers = (
        [State.set_active_tab(tab_value), extra_handler]
        if extra_handler is not None
        else [State.set_active_tab(tab_value)]
    )
    return rx.box(
        rx.hstack(
            rx.icon(
                icon_name,
                size=18,
                color=rx.cond(is_active, styles.NAV_TEXT_ACTIVE, styles.NAV_TEXT_INACTIVE),
            ),
            rx.text(
                label,
                size="2",
                weight=rx.cond(is_active, "medium", "regular"),
                color=rx.cond(is_active, styles.NAV_TEXT_ACTIVE, styles.NAV_TEXT_INACTIVE),
            ),
            spacing="3",
            align="center",
            padding="9px 14px",
            width="100%",
        ),
        border_left=rx.cond(
            is_active,
            f"3px solid {styles.NAV_BORDER_ACTIVE}",
            "3px solid transparent",
        ),
        background=rx.cond(is_active, styles.NAV_BG_ACTIVE, "transparent"),
        border_radius="0 6px 6px 0",
        cursor="pointer",
        _hover={"background": rx.cond(is_active, styles.NAV_BG_ACTIVE, styles.BG_HOVER)},
        on_click=handlers,
        width="100%",
        transition="background 0.15s",
    )


def sidebar() -> rx.Component:
    return rx.box(
        rx.vstack(
            # Brand
            rx.hstack(
                rx.box(
                    rx.icon("house", size=22, color=styles.TEAL_ICON_FG),
                    padding="8px",
                    border_radius="8px",
                    background=styles.TEAL_ICON_BG,
                    display="flex",
                    align_items="center",
                    justify_content="center",
                ),
                rx.vstack(
                    rx.text("WiseWombat", weight="bold", size="3", color=styles.TEXT_PRIMARY),
                    spacing="0",
                ),
                spacing="2",
                align="center",
                padding="18px 16px 14px 16px",
            ),
            rx.separator(size="4"),
            # Navigation
            rx.vstack(
                rx.text(
                    "NAVIGATION",
                    size="1",
                    weight="bold",
                    color=styles.TEXT_FAINT,
                    padding="10px 16px 4px 16px",
                    letter_spacing="0.08em",
                ),
                _nav_item("Chat", "message_square", "chat"),
                _nav_item("Assets", "package", "assets", State.load_assets),
                _nav_item("Schedule", "calendar", "schedule", State.load_schedule),
                rx.cond(
                    State.is_admin,
                    _nav_item("Admin", "users", "admin", State.load_admin_users),
                    rx.fragment(),
                ),
                spacing="1",
                width="100%",
                padding_x="8px",
                padding_y="4px",
            ),
            rx.separator(size="4"),
            # Agent status
            rx.hstack(
                rx.box(
                    width="8px",
                    height="8px",
                    border_radius="50%",
                    background=styles.GREEN_600,
                    flex_shrink="0",
                ),
                rx.text("Agent ready", size="1", color=styles.TEXT_MUTED),
                spacing="2",
                align="center",
                padding="8px 16px",
            ),
            rx.spacer(),
            # User section
            rx.separator(size="4"),
            rx.vstack(
                rx.hstack(
                    rx.avatar(
                        fallback=State.user_email[:2].upper(),
                        size="2",
                        color_scheme=styles.TEAL_ACCENT,
                        variant="soft",
                    ),
                    rx.vstack(
                        rx.text(
                            State.user_email,
                            size="1",
                            weight="medium",
                            color=styles.TEXT_SECONDARY,
                            overflow="hidden",
                            text_overflow="ellipsis",
                            white_space="nowrap",
                            max_width="130px",
                        ),
                        rx.badge(
                            State.user_role,
                            size="1",
                            variant="outline",
                            color_scheme=rx.cond(
                                State.user_role == "admin", "teal", "gray"
                            ),
                        ),
                        spacing="0",
                        align="start",
                    ),
                    spacing="2",
                    align="center",
                    width="100%",
                ),
                rx.button(
                    rx.icon("log_out", size=14),
                    "Log out",
                    on_click=State.logout,
                    size="2",
                    width="100%",
                    variant="ghost",
                    color_scheme="gray",
                ),
                spacing="3",
                width="100%",
                padding="12px 16px",
            ),
            spacing="0",
            align="start",
            width="100%",
            height="100%",
        ),
        width="220px",
        min_height="100vh",
        height="100vh",
        border_right=f"1px solid {styles.BORDER_DEFAULT}",
        background=styles.BG_SURFACE,
        flex_shrink="0",
        position="sticky",
        top="0",
        overflow_y="auto",
    )


# ── Top header bar ─────────────────────────────────────────────────────────────

def top_header_bar() -> rx.Component:
    page_title = rx.cond(
        State.active_tab == "chat", "Chat",
        rx.cond(
            State.active_tab == "assets", "Asset Inventory",
            rx.cond(
                State.active_tab == "schedule", "Maintenance Schedule",
                "User Management",
            ),
        ),
    )
    return rx.box(
        rx.hstack(
            rx.text(page_title, size="4", weight="bold", color=styles.TEXT_PRIMARY),
            rx.spacer(),
            rx.box(
                rx.input(
                    rx.input.slot(rx.icon("search", size=14)),
                    placeholder="Search…",
                    size="2",
                    variant="surface",
                    width="220px",
                ),
            ),
            rx.box(
                rx.icon("bell", size=18, color=styles.TEXT_MUTED),
                padding="6px",
                border_radius="6px",
                cursor="pointer",
                _hover={"background": styles.BG_HOVER},
            ),
            rx.hstack(
                rx.avatar(
                    fallback=State.user_email[:2].upper(),
                    size="2",
                    color_scheme=styles.TEAL_ACCENT,
                    variant="soft",
                ),
                rx.vstack(
                    rx.text(
                        State.user_email,
                        size="1",
                        weight="medium",
                        color=styles.TEXT_SECONDARY,
                        max_width="160px",
                        overflow="hidden",
                        text_overflow="ellipsis",
                        white_space="nowrap",
                    ),
                    rx.text(State.user_role, size="1", color=styles.TEXT_MUTED),
                    spacing="0",
                    align="start",
                ),
                spacing="2",
                align="center",
            ),
            spacing="3",
            align="center",
            width="100%",
            padding="0 24px",
        ),
        background=styles.BG_SURFACE,
        border_bottom=f"1px solid {styles.BORDER_DEFAULT}",
        height="56px",
        width="100%",
        position="sticky",
        top="0",
        z_index="10",
        display="flex",
        align_items="center",
    )


# ── Chat tab ───────────────────────────────────────────────────────────────────

def _tool_call_item(tc: ToolCall) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.badge(tc.step, color_scheme=styles.TEAL_ACCENT, variant="solid", size="1"),
            rx.text(tc.icon, size="2", color=styles.TEXT_SECONDARY),
            rx.code(tc.name, size="1"),
            rx.spacer(),
            rx.text("tool call", size="1", color=styles.TEXT_MUTED),
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
                    rx.icon("check", size=12, color=styles.GREEN_600),
                    rx.text("result", size="1", color=styles.GREEN_600),
                ),
                rx.code_block(
                    tc.result_str,
                    language="json",
                    font_size="11px",
                    can_copy=False,
                ),
                padding_left="1em",
                border_left=f"2px solid {styles.GREEN_600}",
                margin_top="4px",
            ),
            rx.fragment(),
        ),
        border_left=f"3px solid {styles.TEAL_600}",
        padding="10px 14px",
        margin_y="4px",
        border_radius="0 8px 8px 0",
        background=styles.TEAL_TOOL_BG,
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
                "p": lambda text: rx.text(text, size="2", color=styles.TEXT_PRIMARY),
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
                rx.text(msg.content, size="2", color=styles.TEXT_PRIMARY),
                background=styles.TEAL_MSG_BG,
                border=f"1px solid {styles.TEAL_300}",
                border_radius="12px 12px 2px 12px",
                padding="10px 14px",
                max_width="75%",
            ),
            width="100%",
        ),
        rx.hstack(
            rx.avatar(fallback="AI", size="2", color_scheme=styles.TEAL_ACCENT, variant="soft"),
            rx.box(
                _assistant_bubble(msg),
                background=styles.BG_SURFACE,
                border=f"1px solid {styles.BORDER_DEFAULT}",
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
                rx.icon("triangle_alert", size=16, color=styles.ORANGE_600),
                rx.text("Action requires your approval", weight="bold", size="2", color=styles.TEXT_PRIMARY),
                align="center",
                spacing="2",
            ),
            rx.hstack(
                rx.badge(approval.agent_name, color_scheme="orange", size="1"),
                rx.text(approval.request_id, size="1", color=styles.TEXT_FAINT),
                spacing="2",
            ),
            rx.text(approval.action_description, size="2", color=styles.TEXT_SECONDARY),
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
        border=f"1px solid {styles.ORANGE_APPROVAL_BORDER}",
        background=styles.ORANGE_APPROVAL_BG,
    )


def chat_tab() -> rx.Component:
    return rx.vstack(
        rx.scroll_area(
            rx.vstack(
                rx.foreach(State.messages, _chat_message),
                rx.cond(
                    State.is_thinking,
                    rx.hstack(
                        rx.avatar(fallback="AI", size="2",
                                  color_scheme=styles.TEAL_ACCENT, variant="soft"),
                        rx.box(
                            rx.hstack(
                                rx.spinner(size="2"),
                                rx.text("Thinking…", size="2", color=styles.TEXT_MUTED),
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
            height="calc(100vh - 56px - 68px)",
            width="100%",
            background=styles.BG_SURFACE,
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
        rx.box(
            rx.form(
                rx.hstack(
                    rx.input(
                        placeholder="Ask about your home assets…",
                        name="prompt",
                        size="3",
                        flex="1",
                        disabled=State.is_thinking,
                        variant="surface",
                    ),
                    rx.button(
                        rx.icon("send", size=16),
                        type="submit",
                        size="3",
                        color_scheme=styles.TEAL_ACCENT,
                        disabled=State.is_thinking,
                    ),
                    spacing="2",
                    width="100%",
                ),
                on_submit=State.send_message,
                reset_on_submit=True,
                width="100%",
            ),
            padding="12px 16px",
            border_top=f"1px solid {styles.BORDER_DEFAULT}",
            background=styles.BG_SURFACE,
            width="100%",
        ),
        spacing="0",
        width="100%",
        height="100%",
        background=styles.BG_SURFACE,
    )


# ── Assets tab ─────────────────────────────────────────────────────────────────

def _asset_row(asset: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(asset["id"], size="1", color=styles.TEXT_FAINT)),
        rx.table.cell(
            rx.badge(
                asset["name"],
                style={**styles.BADGE_TEAL, "font-weight": "500"},
                size="1",
            )
        ),
        rx.table.cell(
            rx.badge(
                asset["category"],
                style=styles.BADGE_CATEGORY,
                size="1",
            )
        ),
        rx.table.cell(rx.text(asset["brand"], size="2", color=styles.TEXT_SECONDARY)),
        rx.table.cell(rx.text(asset["location"], size="2", color=styles.TEXT_SECONDARY)),
        rx.table.cell(rx.text(asset["purchase_date"], size="2", color=styles.TEXT_SECONDARY)),
        rx.table.cell(rx.text(asset["warranty_expiry"], size="2", color=styles.TEXT_SECONDARY)),
        on_click=State.select_asset(asset["name"]),
        cursor="pointer",
        _hover={"background": styles.TEAL_50},
    )


def _asset_detail() -> rx.Component:
    return rx.cond(
        State.has_selected_asset,
        rx.card(
            rx.vstack(
                # Icon circle header
                rx.hstack(
                    rx.box(
                        rx.icon("package_open", size=26, color=styles.TEAL_ICON_FG),
                        padding="10px",
                        border_radius="10px",
                        background=styles.TEAL_ICON_BG,
                        display="flex",
                        align_items="center",
                        justify_content="center",
                    ),
                    rx.vstack(
                        rx.text(
                            State.selected_asset["name"],
                            weight="bold",
                            size="4",
                            color=styles.TEXT_PRIMARY,
                        ),
                        rx.badge(
                            State.selected_asset["category"],
                            style=styles.BADGE_TEAL,
                            size="1",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    spacing="3",
                    align="center",
                    width="100%",
                ),
                rx.separator(size="4"),
                rx.grid(
                    rx.vstack(
                        rx.text("Brand", size="1", color=styles.TEXT_FAINT, weight="bold"),
                        rx.text(State.selected_asset["brand"], size="2", color=styles.TEXT_SECONDARY),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Model", size="1", color=styles.TEXT_FAINT, weight="bold"),
                        rx.text(State.selected_asset["model"], size="2", color=styles.TEXT_SECONDARY),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Location", size="1", color=styles.TEXT_FAINT, weight="bold"),
                        rx.text(State.selected_asset["location"], size="2", color=styles.TEXT_SECONDARY),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Purchased", size="1", color=styles.TEXT_FAINT, weight="bold"),
                        rx.text(State.selected_asset["purchase_date"], size="2", color=styles.TEXT_SECONDARY),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Price", size="1", color=styles.TEXT_FAINT, weight="bold"),
                        rx.text(State.selected_asset["purchase_price"], size="2", color=styles.TEXT_SECONDARY),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Warranty", size="1", color=styles.TEXT_FAINT, weight="bold"),
                        rx.text(State.selected_asset["warranty_expiry"], size="2", color=styles.TEXT_SECONDARY),
                        spacing="1",
                    ),
                    columns="3",
                    spacing="4",
                    width="100%",
                ),
                rx.cond(
                    State.selected_asset["notes"] != "",
                    rx.box(
                        rx.text(State.selected_asset["notes"], size="2", color=styles.TEXT_SECONDARY),
                        border_left=f"3px solid {styles.TEAL_600}",
                        padding_left="12px",
                    ),
                    rx.fragment(),
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            background=styles.BG_SURFACE,
            border=f"1px solid {styles.BORDER_DEFAULT}",
        ),
        rx.callout(
            "Select an asset from the table to view its details.",
            icon="info",
            color_scheme="gray",
        ),
    )


def assets_tab() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.box(
                rx.select(
                    CATEGORIES,
                    value=State.asset_category,
                    on_change=State.set_asset_category,
                    size="2",
                    width="200px",
                ),
            ),
            rx.spacer(),
            rx.card(
                rx.hstack(
                    rx.text(
                        State.asset_count,
                        size="5",
                        weight="bold",
                        color=styles.TEAL_700,
                    ),
                    rx.text("assets", size="2", color=styles.TEXT_MUTED),
                    spacing="2",
                    align="center",
                ),
                padding="8px 18px",
                background=styles.TEAL_50,
                border=f"1px solid {styles.TEAL_300}",
            ),
            align="center",
            width="100%",
        ),
        rx.cond(
            State.asset_count == 0,
            rx.callout(
                "No assets found. Ask the chat agent to add some!",
                icon="package_open",
                color_scheme="gray",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell(rx.text("ID", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                        rx.table.column_header_cell(rx.text("NAME", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                        rx.table.column_header_cell(rx.text("CATEGORY", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                        rx.table.column_header_cell(rx.text("BRAND", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                        rx.table.column_header_cell(rx.text("LOCATION", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                        rx.table.column_header_cell(rx.text("PURCHASED", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                        rx.table.column_header_cell(rx.text("WARRANTY", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                    ),
                ),
                rx.table.body(
                    rx.foreach(State.display_assets, _asset_row),
                ),
                width="100%",
                size="2",
                variant="surface",
            ),
        ),
        rx.separator(size="4"),
        _asset_detail(),
        spacing="4",
        align="start",
        width="100%",
        padding="20px 24px",
    )


# ── Schedule tab ───────────────────────────────────────────────────────────────

def _task_card(task: dict) -> rx.Component:
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.text(task["asset_name"], weight="bold", size="2", color=styles.TEXT_PRIMARY),
                    rx.text("·", size="2", color=styles.TEXT_MUTED),
                    rx.text(task["task_name"], size="2", color=styles.TEXT_SECONDARY),
                    spacing="2",
                    flex_wrap="wrap",
                ),
                rx.hstack(
                    rx.badge(task["category"], size="1", style=styles.BADGE_CATEGORY),
                    rx.text("Last: ", task["completed_date"], size="1", color=styles.TEXT_MUTED),
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
                        rx.cond(task["urgency"] == "due_soon", "orange", "green"),
                    ),
                    variant=rx.cond(
                        task["urgency"] == "overdue", "solid", "soft"
                    ),
                    size="1",
                ),
                rx.text(task["due_label"], size="1", color=styles.TEXT_MUTED, text_align="right"),
                spacing="1",
                align="end",
            ),
            align="center",
            width="100%",
        ),
        border_left=rx.cond(
            task["urgency"] == "overdue",
            f"4px solid {styles.RED_600}",
            rx.cond(
                task["urgency"] == "due_soon",
                f"4px solid {styles.ORANGE_600}",
                f"4px solid {styles.GREEN_600}",
            ),
        ),
        background=styles.BG_SURFACE,
        border_top=f"1px solid {styles.BORDER_DEFAULT}",
        border_right=f"1px solid {styles.BORDER_DEFAULT}",
        border_bottom=f"1px solid {styles.BORDER_DEFAULT}",
        _hover={"border_color": styles.BORDER_STRONG},
    )


def schedule_tab() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text("Show tasks due within:", size="2", color=styles.TEXT_MUTED),
            rx.slider(
                min=7,
                max=365,
                value=[State.schedule_days],
                on_value_commit=State.set_schedule_days,
                width="200px",
            ),
            rx.text(State.schedule_days, " days", size="2", color=styles.TEAL_700),
            rx.button(
                rx.icon("refresh_cw", size=14),
                "Refresh",
                on_click=State.load_schedule,
                size="2",
                variant="soft",
                color_scheme=styles.TEAL_ACCENT,
            ),
            spacing="4",
            align="center",
            flex_wrap="wrap",
        ),
        rx.grid(
            rx.card(
                rx.vstack(
                    rx.text(State.overdue_count, size="7", weight="bold", color=styles.RED_600),
                    rx.text("Overdue", size="1", color=styles.TEXT_MUTED, weight="bold"),
                    align="center",
                    spacing="1",
                ),
                background=styles.RED_BG,
                border=f"1px solid {styles.RED_BORDER}",
            ),
            rx.card(
                rx.vstack(
                    rx.text(State.due_soon_count, size="7", weight="bold", color=styles.ORANGE_600),
                    rx.text("Due this week", size="1", color=styles.TEXT_MUTED, weight="bold"),
                    align="center",
                    spacing="1",
                ),
                background=styles.ORANGE_BG,
                border=f"1px solid {styles.ORANGE_BORDER}",
            ),
            rx.card(
                rx.vstack(
                    rx.text(State.upcoming_count, size="7", weight="bold", color=styles.GREEN_600),
                    rx.text("Upcoming", size="1", color=styles.TEXT_MUTED, weight="bold"),
                    align="center",
                    spacing="1",
                ),
                background=styles.GREEN_BG,
                border=f"1px solid {styles.GREEN_BORDER}",
            ),
            columns="3",
            spacing="3",
            width="100%",
        ),
        rx.cond(
            State.upcoming_count + State.overdue_count + State.due_soon_count == 0,
            rx.callout(
                "No maintenance tasks due in this period.",
                icon="circle_check",
                color_scheme="green",
            ),
            rx.vstack(
                rx.foreach(State.tasks, _task_card),
                spacing="2",
                width="100%",
            ),
        ),
        spacing="4",
        align="start",
        width="100%",
        padding="20px 24px",
    )


# ── Admin tab ──────────────────────────────────────────────────────────────────

def _user_row(user: UserRow) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(user.email, size="2", weight="medium", color=styles.TEXT_PRIMARY)),
        rx.table.cell(
            rx.badge(
                user.role,
                color_scheme=rx.cond(user.role == "admin", "teal", "gray"),
                variant="soft",
                size="1",
            ),
        ),
        rx.table.cell(
            rx.badge(
                rx.cond(user.is_active, "Active", "Inactive"),
                color_scheme=rx.cond(user.is_active, "green", "red"),
                variant="outline",
                size="1",
            ),
        ),
        rx.table.cell(rx.text(user.created_at, size="1", color=styles.TEXT_FAINT)),
        rx.table.cell(
            rx.hstack(
                rx.button(
                    rx.cond(user.role == "admin", "Make User", "Make Admin"),
                    on_click=State.toggle_user_role(user.id, user.role),
                    size="1",
                    variant="ghost",
                    color_scheme=styles.TEAL_ACCENT,
                ),
                rx.button(
                    rx.cond(user.is_active, "Deactivate", "Activate"),
                    on_click=State.toggle_user_active(user.id, user.is_active),
                    size="1",
                    variant="ghost",
                    color_scheme=rx.cond(user.is_active, "red", "green"),
                ),
                spacing="1",
            ),
        ),
        _hover={"background": styles.BG_ROW_HOVER},
    )


def admin_tab() -> rx.Component:
    return rx.vstack(
        rx.cond(
            State.admin_error != "",
            rx.callout(State.admin_error, color_scheme="red", icon="circle_x"),
            rx.fragment(),
        ),
        rx.cond(
            State.admin_success != "",
            rx.callout(State.admin_success, color_scheme="green", icon="circle_check"),
            rx.fragment(),
        ),
        rx.card(
            rx.vstack(
                rx.text("Create new user", weight="bold", size="3", color=styles.TEXT_PRIMARY),
                rx.form(
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
                            rx.icon("user_plus", size=14),
                            "Create",
                            type="submit",
                            size="2",
                            color_scheme=styles.TEAL_ACCENT,
                        ),
                        spacing="2",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    on_submit=State.create_user,
                    reset_on_submit=True,
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            background=styles.BG_SURFACE,
            border=f"1px solid {styles.BORDER_DEFAULT}",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell(rx.text("EMAIL", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                    rx.table.column_header_cell(rx.text("ROLE", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                    rx.table.column_header_cell(rx.text("STATUS", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                    rx.table.column_header_cell(rx.text("CREATED", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                    rx.table.column_header_cell(rx.text("ACTIONS", size="1", weight="bold", color=styles.TEXT_SECONDARY)),
                ),
            ),
            rx.table.body(
                rx.foreach(State.admin_users, _user_row),
            ),
            width="100%",
            size="2",
            variant="surface",
        ),
        spacing="4",
        align="start",
        width="100%",
        padding="20px 24px",
        on_mount=State.load_admin_users,
    )


# ── Main page ──────────────────────────────────────────────────────────────────

def index_page() -> rx.Component:
    return rx.cond(
        State.is_authenticated,
        rx.hstack(
            sidebar(),
            rx.vstack(
                top_header_bar(),
                rx.box(
                    rx.tabs.root(
                        rx.tabs.list(display="none"),
                        rx.tabs.content(chat_tab(), value="chat"),
                        rx.tabs.content(assets_tab(), value="assets"),
                        rx.tabs.content(schedule_tab(), value="schedule"),
                        rx.cond(
                            State.is_admin,
                            rx.tabs.content(admin_tab(), value="admin"),
                            rx.fragment(),
                        ),
                        value=State.active_tab,
                        width="100%",
                        height="100%",
                    ),
                    flex="1",
                    overflow="auto",
                    width="100%",
                    background=styles.BG_PAGE,
                ),
                spacing="0",
                width="100%",
                height="100vh",
                overflow="hidden",
            ),
            spacing="0",
            align="start",
            width="100%",
            height="100vh",
            overflow="hidden",
            background=styles.BG_PAGE,
        ),
        rx.center(
            rx.vstack(
                rx.spinner(size="3"),
                rx.text("Redirecting to login…", color=styles.TEXT_MUTED),
                spacing="3",
                align="center",
            ),
            min_height="100vh",
        ),
    )
