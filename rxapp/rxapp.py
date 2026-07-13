"""Reflex app entry point - registers pages and bootstraps the database."""

import reflex as rx
from dotenv import load_dotenv
from rxapp import styles

load_dotenv()

# Bootstrap DB and (optionally) RAG index before the app starts
from db_init import init_db  # noqa: E402
init_db()
try:
    from knowledge.rag.indexer import index_all
    index_all()
except Exception:
    pass

from rxapp.login_page import login_page  # noqa: E402
from rxapp.index_page import index_page  # noqa: E402
from rxapp.state import State  # noqa: E402

app = rx.App(
    head_components=[
        rx.el.meta(name="color-scheme", content="light only"),
        rx.el.style(f"""
            /* ── Inputs ── */
            .rt-TextFieldInput {{
                color: {styles.TEXT_PRIMARY} !important;
                -webkit-text-fill-color: {styles.TEXT_PRIMARY} !important;
            }}
            .rt-TextFieldInput::placeholder {{
                color: {styles.TEXT_MUTED} !important;
                -webkit-text-fill-color: {styles.TEXT_MUTED} !important;
                opacity: 1 !important;
            }}

            /* ── Select ── */
            .rt-SelectTrigger, .rt-SelectTriggerInner {{
                color: {styles.TEXT_PRIMARY} !important;
                -webkit-text-fill-color: {styles.TEXT_PRIMARY} !important;
            }}
            .rt-SelectContent, .rt-SelectItem, .rt-SelectItemText {{
                color: {styles.TEXT_PRIMARY} !important;
                background-color: {styles.BG_SURFACE} !important;
            }}
            .rt-SelectItem[data-highlighted] {{
                background-color: {styles.TEAL_50} !important;
            }}

            /* ── Badges ── */
            .rt-Badge[data-accent-color="gray"] {{
                background-color: {styles.BG_SUBTLE} !important;
                color: {styles.TEXT_SECONDARY} !important;
                border-color: {styles.BORDER_MUTED} !important;
            }}
            .rt-Badge[data-accent-color="green"] {{
                color: {styles.GREEN_800} !important;
                border-color: {styles.GREEN_BORDER} !important;
            }}
            .rt-Badge[data-accent-color="red"] {{
                color: {styles.RED_800} !important;
                border-color: {styles.RED_BORDER} !important;
            }}
            .rt-Badge[data-accent-color="teal"] {{
                color: {styles.TEAL_900} !important;
            }}

            /* ── Ghost buttons ── */
            .rt-Button.rt-variant-ghost[data-accent-color="teal"] {{
                color: {styles.TEAL_700} !important;
            }}
            .rt-Button.rt-variant-ghost[data-accent-color="red"] {{
                color: {styles.RED_600} !important;
            }}
            .rt-Button.rt-variant-ghost[data-accent-color="green"] {{
                color: {styles.GREEN_600} !important;
            }}

            /* ── Callouts ── */
            .rt-CalloutRoot[data-accent-color="green"] .rt-CalloutText,
            .rt-CalloutRoot[data-accent-color="green"] svg {{
                color: {styles.GREEN_800} !important;
                stroke: {styles.GREEN_800} !important;
            }}
            .rt-CalloutRoot[data-accent-color="gray"] .rt-CalloutText,
            .rt-CalloutRoot[data-accent-color="gray"] svg {{
                color: {styles.TEXT_SECONDARY} !important;
                stroke: {styles.TEXT_SECONDARY} !important;
            }}
        """),
    ],
)

app.add_page(login_page, route="/login", title="Login - WiseWombat")
app.add_page(
    index_page,
    route="/",
    title="WiseWombat",
    on_load=State.require_auth,
)
