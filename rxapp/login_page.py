"""Login page component."""

import reflex as rx
from rxapp.state import State


def login_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.text("🏠", font_size="2em"),
                    rx.vstack(
                        rx.heading("Home Asset Agent", size="5"),
                        rx.text(
                            "Sign in to manage your home assets",
                            color_scheme="gray",
                            size="2",
                        ),
                        spacing="0",
                        align="start",
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.separator(size="4"),
                # Error banner
                rx.cond(
                    State.login_error != "",
                    rx.callout(
                        State.login_error,
                        color="red",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                # Login form
                rx.form(
                    rx.vstack(
                        rx.text("Email", size="2", weight="medium"),
                        rx.input(
                            placeholder="you@example.com",
                            name="email",
                            type="email",
                            size="3",
                            width="100%",
                        ),
                        rx.text("Password", size="2", weight="medium"),
                        rx.input(
                            placeholder="••••••••",
                            name="password",
                            type="password",
                            size="3",
                            width="100%",
                        ),
                        rx.button(
                            "Sign in",
                            type="submit",
                            size="3",
                            width="100%",
                            color_scheme="violet",
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    on_submit=State.login,
                    reset_on_submit=False,
                ),
                rx.text(
                    "Accounts are created by an admin — no self-registration.",
                    size="1",
                    color_scheme="gray",
                    text_align="center",
                ),
                spacing="4",
                width="100%",
                min_width="360px",
            ),
            size="4",
        ),
        min_height="100vh",
    )
