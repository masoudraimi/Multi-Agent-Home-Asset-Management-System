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

st.markdown("""
<style>
/* ── Layout ─────────────────────────────────────── */
.block-container { padding-top: 4rem !important; padding-bottom: 2rem !important; }

/* ── Smooth transitions ─────────────────────────── */
*, *::before, *::after {
    transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

/* ── Scrollbar ──────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(108,99,255,0.5); }

/* ── Tabs ───────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
    padding-bottom: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0 !important;
    padding: 8px 18px !important;
    font-weight: 500;
    color: rgba(255,255,255,0.55) !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(108,99,255,0.15) !important;
    color: #a09af0 !important;
    border-bottom: 2px solid #6C63FF !important;
}

/* ── Buttons ────────────────────────────────────── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(108,99,255,0.35) !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6C63FF, #8b85ff) !important;
    border: none !important;
}

/* ── Bordered containers ────────────────────────── */
[data-testid="stVerticalBlock"] > div > [data-testid="stVerticalBlockBorderWrapper"] > div {
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.25) !important;
    background: rgba(255,255,255,0.02) !important;
}

/* ── Metric tiles ───────────────────────────────── */
[data-testid="metric-container"] {
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    background: rgba(255,255,255,0.025) !important;
}
[data-testid="metric-container"] label {
    color: rgba(255,255,255,0.5) !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 26px !important;
    font-weight: 700 !important;
    color: #E6EDF3 !important;
}

/* ── Expanders ──────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 8px !important;
    background: rgba(255,255,255,0.02) !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    font-size: 13px !important;
    padding: 8px 12px !important;
}
[data-testid="stExpander"] summary:hover {
    background: rgba(108,99,255,0.08) !important;
}

/* ── Sidebar ────────────────────────────────────── */
[data-testid="stSidebar"] {
    border-right: 1px solid rgba(255,255,255,0.07) !important;
    background: rgba(22,27,34,0.95) !important;
}

/* ── Chat messages ──────────────────────────────── */
[data-testid="stChatMessage"] {
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    margin-bottom: 6px !important;
    padding: 12px 16px !important;
    background: rgba(255,255,255,0.02) !important;
}

/* ── Chat input ─────────────────────────────────── */
[data-testid="stChatInputContainer"] > div {
    border-radius: 12px !important;
    border: 1px solid rgba(108,99,255,0.35) !important;
    background: rgba(108,99,255,0.05) !important;
}
[data-testid="stChatInputContainer"] > div:focus-within {
    border-color: #6C63FF !important;
    box-shadow: 0 0 0 3px rgba(108,99,255,0.2) !important;
}

/* ── Dataframes ─────────────────────────────────── */
[data-testid="stDataFrame"] > div {
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    overflow: hidden !important;
}

/* ── Selectbox / Slider ─────────────────────────── */
[data-testid="stSelectbox"] > div > div {
    border-radius: 8px !important;
    border-color: rgba(255,255,255,0.12) !important;
}
[data-testid="stSlider"] [role="slider"] {
    background: #6C63FF !important;
}

/* ── Success / Info / Error banners ─────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border-left-width: 4px !important;
}

/* ── Divider ────────────────────────────────────── */
hr { border-color: rgba(255,255,255,0.08) !important; }
</style>
""", unsafe_allow_html=True)

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
tab_labels = ["💬 Chat", "📦 Assets", "🗓 Schedule", "📊 Performance"]
if is_admin:
    tab_labels += ["🔭 Observability", "👤 Admin"]

tabs = st.tabs(tab_labels)

with tabs[0]:
    render_chat_tab()

with tabs[1]:
    render_assets_tab()

with tabs[2]:
    render_schedule_tab()

with tabs[3]:
    render_performance_tab()

if is_admin:
    with tabs[4]:
        render_observability_tab()
    with tabs[5]:
        render_admin_tab(user)
