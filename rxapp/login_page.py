"""Login page component."""

import reflex as rx
from rxapp.state import State
from rxapp.styles import (
    TEXT_PRIMARY, TEXT_MUTED, TEXT_SECONDARY,
    TEAL_ICON_BG, TEAL_ICON_FG, TEAL_ACCENT,
    BORDER_DEFAULT, BG_PAGE, BG_SURFACE, SHADOW_CARD,
)


def login_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                # Header - icon + title centered
                rx.vstack(
                    rx.box(
                        rx.icon("house", size=32, color=TEAL_ICON_FG),
                        padding="12px",
                        border_radius="12px",
                        background=TEAL_ICON_BG,
                        display="flex",
                        align_items="center",
                        justify_content="center",
                    ),
                    rx.heading(
                        "WiseWombat",
                        size="6",
                        weight="bold",
                        color=TEXT_PRIMARY,
                        text_align="center",
                    ),
                    rx.text(
                        "Sign in to manage your home assets",
                        color=TEXT_MUTED,
                        size="2",
                        text_align="center",
                    ),
                    spacing="2",
                    align="center",
                    width="100%",
                ),
                rx.separator(size="4", color=BORDER_DEFAULT),
                # Error banner
                rx.cond(
                    State.login_error != "",
                    rx.callout(
                        State.login_error,
                        color_scheme="red",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                # Login form
                rx.form(
                    rx.vstack(
                        rx.vstack(
                            rx.text(
                                "Email",
                                size="2",
                                weight="medium",
                                color=TEXT_SECONDARY,
                            ),
                            rx.input(
                                placeholder="you@example.com",
                                name="email",
                                type="email",
                                size="3",
                                width="100%",
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text(
                                "Password",
                                size="2",
                                weight="medium",
                                color=TEXT_SECONDARY,
                            ),
                            rx.input(
                                placeholder="••••••••",
                                name="password",
                                type="password",
                                size="3",
                                width="100%",
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.button(
                            rx.icon("log_in", size=16),
                            "Sign in",
                            type="submit",
                            size="3",
                            width="100%",
                            color_scheme=TEAL_ACCENT,
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    on_submit=State.login,
                    reset_on_submit=False,
                ),
                rx.text(
                    "Accounts are created by an admin. No self-registration.",
                    size="1",
                    color=TEXT_MUTED,
                    text_align="center",
                ),
                spacing="5",
                width="100%",
                min_width="360px",
                padding="8px",
            ),
            size="4",
            background=BG_SURFACE,
            border=f"1px solid {BORDER_DEFAULT}",
            box_shadow=SHADOW_CARD,
        ),
        background=BG_PAGE,
        min_height="100vh",
        width="100%",
    )
