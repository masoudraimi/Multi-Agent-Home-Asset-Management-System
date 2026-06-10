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
from components.performance_tab import render_performance_tab
from components.schedule_tab import render_schedule_tab
from db_init import DB_PATH, init_db

# Ensure DB exists
if not DB_PATH.exists():
    init_db()

# Sidebar
with st.sidebar:
    st.title("🏠 Home Asset Agent")
    st.caption("AI-powered home maintenance manager")
    st.divider()

    if not os.environ.get("OPENROUTER_API_KEY"):
        st.error("OPENROUTER_API_KEY not set. Add it to your .env file.")
        st.stop()

    st.success("Agent ready")
    st.divider()
    st.markdown(
        """**Example queries:**
- *What maintenance is due this month?*
- *When does my dishwasher warranty expire?*
- *How much have I spent on the car?*
- *Log that I replaced the HVAC filters today*
- *Which assets have expired warranties?*
"""
    )

    if st.button("Clear conversation", use_container_width=True):
        for key in ["context", "chat_messages", "turn_metrics"]:
            st.session_state.pop(key, None)
        st.rerun()

# Tabs
tab_chat, tab_assets, tab_schedule, tab_performance = st.tabs([
    "💬 Chat", "📦 Assets", "🗓 Schedule", "📊 Performance"
])

with tab_chat:
    render_chat_tab()

with tab_assets:
    render_assets_tab()

with tab_schedule:
    render_schedule_tab()

with tab_performance:
    render_performance_tab()
