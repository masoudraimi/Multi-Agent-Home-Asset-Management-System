import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="Home Asset Agent",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

from components.admin_tab import render_admin_tab
from components.assets_tab import render_assets_tab
from components.chat_tab import render_chat_tab
from components.login import logout, require_login
from components.observability_tab import render_observability_tab
from components.performance_tab import render_performance_tab
from components.schedule_tab import render_schedule_tab
from core.session import set_current_user
from db_init import init_db

init_db()

# Index knowledge base into semantic memory (shared/global; no-op if already indexed)
try:
    from knowledge.rag.indexer import index_all
    index_all()
except Exception:
    pass

# --- Authentication gate ---------------------------------------------------
# Blocks the app until a valid user is signed in. Accounts are admin-created.
user = require_login()

# Scope every in-process DB call this rerun to the logged-in user.
set_current_user(user["id"])
is_admin = user["role"] == "admin"

# Sidebar
with st.sidebar:
    st.title("🏠 Home Asset Agent")
    st.caption("AI-powered home maintenance manager")
    st.divider()

    st.markdown(f"Signed in as **{user['email']}**")
    st.caption(f"Role: {user['role']}")
    if st.button("Log out", use_container_width=True):
        logout()
        st.rerun()
    st.divider()

    from core.models import Provider, get_provider
    _provider = get_provider()
    if _provider == Provider.OPENROUTER and not os.environ.get("OPENROUTER_API_KEY"):
        st.error("OPENROUTER_API_KEY not set. Add it to your .env file.")
        st.stop()
    elif _provider == Provider.CLAUDE_SDK and not os.environ.get("ANTHROPIC_API_KEY"):
        st.error("ANTHROPIC_API_KEY not set. Add it to your .env file.")
        st.stop()

    st.success("Agent ready")
    st.divider()
    st.markdown(
        """**Example queries:**
- *What maintenance is due this month?*
- *When does my dishwasher warranty expire?*
- *How much have I spent on the car?*
- *I want to add a new dishwasher*
- *What plants do I have? When should I fertilise the lemon tree?*
- *What home assets am I missing?*
"""
    )

    if st.button("Clear conversation", use_container_width=True):
        for key in ["context", "chat_messages", "turn_metrics"]:
            st.session_state.pop(key, None)
        st.rerun()

# Tabs
tab_labels = ["💬 Chat", "📦 Assets", "🗓 Schedule", "📊 Performance", "🔭 Observability"]
if is_admin:
    tab_labels.append("👤 Admin")

tabs = st.tabs(tab_labels)

with tabs[0]:
    render_chat_tab()

with tabs[1]:
    render_assets_tab()

with tabs[2]:
    render_schedule_tab()

with tabs[3]:
    render_performance_tab()

with tabs[4]:
    render_observability_tab()

if is_admin:
    with tabs[5]:
        render_admin_tab(user)
