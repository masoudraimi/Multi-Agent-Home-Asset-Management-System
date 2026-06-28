"""Login gate. Renders a login form and blocks the app until authenticated.

Accounts are created only by an admin (see components/admin_tab.py) — there is
no public sign-up.
"""

import streamlit as st

from core.auth import authenticate

_SESSION_KEY = "auth_user"


def current_user() -> dict | None:
    return st.session_state.get(_SESSION_KEY)


def logout() -> None:
    for key in [_SESSION_KEY, "context", "chat_messages", "turn_metrics", "pending_approvals"]:
        st.session_state.pop(key, None)


def require_login() -> dict:
    """Return the logged-in user, or render the login form and st.stop()."""
    user = current_user()
    if user:
        return user

    st.title("🏠 Home Asset Agent")
    st.caption("Sign in to manage your home assets")

    with st.form("login_form"):
        email = st.text_input("Email", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")

    if submitted:
        user = authenticate(email, password)
        if user:
            st.session_state[_SESSION_KEY] = user
            st.rerun()
        else:
            st.error("Invalid email or password, or your account is inactive.")

    st.stop()
