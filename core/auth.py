"""Self-managed authentication — delegates all DB operations to the active provider.

Business-level validation (email format, password length, last-admin guard) lives
here. DB operations are provider-agnostic via db.get_provider().
"""
from __future__ import annotations

import os

import bcrypt

from db import get_provider


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate(email: str, password: str) -> dict | None:
    """Return the public user dict on valid credentials + active account, else None."""
    email = (email or "").strip().lower()
    if not email or not password:
        return None
    return get_provider().authenticate(email, password)


# ---------------------------------------------------------------------------
# Admin operations
# ---------------------------------------------------------------------------

def list_users() -> list[dict]:
    return get_provider().list_users()


def get_user(user_id: str) -> dict | None:
    return get_provider().get_user(user_id)


def email_exists(email: str) -> bool:
    return get_provider().email_exists((email or "").strip().lower())


def create_user(email: str, password: str, role: str = "user") -> dict:
    """Create a new user. Raises ValueError on bad input / duplicate email."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("A valid email address is required.")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if role not in ("admin", "user"):
        raise ValueError("Role must be 'admin' or 'user'.")
    if email_exists(email):
        raise ValueError(f"A user with email '{email}' already exists.")
    return get_provider().create_user(email, password, role)


def set_active(user_id: str, is_active: bool) -> None:
    if not is_active and get_provider().is_last_active_admin(user_id):
        raise ValueError("Cannot deactivate the last active admin.")
    get_provider().set_active(user_id, is_active)


def set_role(user_id: str, role: str) -> None:
    if role not in ("admin", "user"):
        raise ValueError("Role must be 'admin' or 'user'.")
    if role != "admin" and get_provider().is_last_active_admin(user_id):
        raise ValueError("Cannot demote the last active admin.")
    get_provider().set_role(user_id, role)


def reset_password(user_id: str, new_password: str) -> None:
    if not new_password or len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    get_provider().reset_password(user_id, new_password)


def delete_user(user_id: str) -> None:
    """Delete a user. Their assets/maintenance/agent_memory cascade-delete (FK)."""
    if get_provider().is_last_active_admin(user_id):
        raise ValueError("Cannot delete the last active admin.")
    get_provider().delete_user(user_id)


# ---------------------------------------------------------------------------
# First-run bootstrap
# ---------------------------------------------------------------------------

def bootstrap_admin() -> None:
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD if no users exist."""
    get_provider().bootstrap_admin()
