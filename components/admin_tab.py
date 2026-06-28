"""Admin tab: user management UI. Rendered only for admin-role users."""

import streamlit as st

from core import auth


def render_admin_tab(current_user: dict) -> None:
    st.subheader("User Management")

    _render_create_user()
    st.divider()
    _render_user_list(current_user)


def _render_create_user() -> None:
    with st.expander("➕ Create a new user", expanded=False):
        with st.form("create_user_form", clear_on_submit=True):
            email = st.text_input("Email")
            col1, col2 = st.columns(2)
            password = col1.text_input("Temporary password", type="password")
            role = col2.selectbox("Role", ["user", "admin"])
            submitted = st.form_submit_button("Create user", type="primary")

        if submitted:
            try:
                user = auth.create_user(email, password, role)
                st.success(f"Created {user['role']} account: {user['email']}")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def _render_user_list(current_user: dict) -> None:
    users = auth.list_users()
    st.caption(f"{len(users)} user(s)")

    for user in users:
        is_self = user["id"] == current_user["id"]
        status = "🟢 Active" if user["is_active"] else "⚪ Inactive"
        with st.container(border=True):
            top = st.columns([3, 1, 1])
            with top[0]:
                label = f"**{user['email']}**"
                if is_self:
                    label += " *(you)*"
                st.markdown(label)
                st.caption(f"Role: {user['role']} · {status} · joined {user['created_at'][:10]}")

            # Toggle role
            with top[1]:
                new_role = "user" if user["role"] == "admin" else "admin"
                if st.button(f"Make {new_role}", key=f"role_{user['id']}", use_container_width=True):
                    _try(lambda: auth.set_role(user["id"], new_role))

            # Toggle active
            with top[2]:
                if user["is_active"]:
                    if st.button("Deactivate", key=f"deact_{user['id']}", use_container_width=True):
                        _try(lambda: auth.set_active(user["id"], False))
                else:
                    if st.button("Activate", key=f"act_{user['id']}", use_container_width=True):
                        _try(lambda: auth.set_active(user["id"], True))

            with st.expander("Manage", expanded=False):
                # Reset password
                with st.form(f"pwd_{user['id']}", clear_on_submit=True):
                    new_pwd = st.text_input("New password", type="password", key=f"pwdinput_{user['id']}")
                    if st.form_submit_button("Reset password"):
                        _try(lambda: auth.reset_password(user["id"], new_pwd))

                # Delete
                st.caption("Deleting a user permanently removes their assets and history.")
                confirm = st.checkbox("I understand", key=f"delconf_{user['id']}")
                if st.button("Delete user", key=f"del_{user['id']}", type="secondary", disabled=not confirm):
                    _try(lambda: auth.delete_user(user["id"]))


def _try(action) -> None:
    """Run an admin action, surface ValueError as an error, and rerun on success."""
    try:
        action()
        st.rerun()
    except ValueError as e:
        st.error(str(e))
