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

from components.assets_tab import render_assets_tab
from components.chat_tab import render_chat_tab
from components.observability_tab import render_observability_tab
from components.performance_tab import render_performance_tab
from components.schedule_tab import render_schedule_tab
from db_init import init_db

init_db()

# Index knowledge base into semantic memory (no-op if already indexed)
try:
    from knowledge.rag.indexer import index_all
    index_all()
except Exception:
    pass

# Sidebar
with st.sidebar:
    st.title("🏠 Home Asset Agent")
    st.caption("AI-powered home maintenance manager")
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
tab_chat, tab_assets, tab_schedule, tab_performance, tab_obs = st.tabs([
    "💬 Chat", "📦 Assets", "🗓 Schedule", "📊 Performance", "🔭 Observability"
])

with tab_chat:
    render_chat_tab()

with tab_assets:
    render_assets_tab()

with tab_schedule:
    render_schedule_tab()

with tab_performance:
    render_performance_tab()

with tab_obs:
    render_observability_tab()
