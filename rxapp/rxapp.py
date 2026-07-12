"""Reflex app entry point — registers pages and bootstraps the database."""

import reflex as rx
from dotenv import load_dotenv

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

app = rx.App()

app.add_page(login_page, route="/login", title="Login — Home Asset Agent")
app.add_page(
    index_page,
    route="/",
    title="Home Asset Agent",
    on_load=State.require_auth,
)
