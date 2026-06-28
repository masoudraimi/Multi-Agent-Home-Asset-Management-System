"""Self-managed authentication against the `users` table.

Passwords are hashed with bcrypt. There is no public sign-up — accounts are
created only by an admin (or the env-bootstrapped first admin). All operations
use the service-role Supabase client.
"""

from __future__ import annotations

import os

import bcrypt

from db_conn import get_client

# Columns safe to expose to the UI / session (never includes password_hash).
_PUBLIC_COLS = "id, email, role, is_active, created_at"


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

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
    rows = (
        get_client()
        .table("users")
        .select("id, email, role, is_active, created_at, password_hash")
        .eq("email", email)
        .execute()
        .data
    )
    if not rows:
        return None
    user = rows[0]
    if not user.get("is_active"):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    user.pop("password_hash", None)
    return user


# ---------------------------------------------------------------------------
# Admin operations
# ---------------------------------------------------------------------------

def list_users() -> list[dict]:
    return (
        get_client()
        .table("users")
        .select(_PUBLIC_COLS)
        .order("created_at")
        .execute()
        .data
    )


def get_user(user_id: str) -> dict | None:
    rows = get_client().table("users").select(_PUBLIC_COLS).eq("id", user_id).execute().data
    return rows[0] if rows else None


def email_exists(email: str) -> bool:
    email = (email or "").strip().lower()
    rows = get_client().table("users").select("id").eq("email", email).execute().data
    return bool(rows)


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

    row = {
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
    }
    inserted = get_client().table("users").insert(row).execute().data[0]
    return {k: inserted[k] for k in ("id", "email", "role", "is_active", "created_at")}


def set_active(user_id: str, is_active: bool) -> None:
    if not is_active and _is_last_active_admin(user_id):
        raise ValueError("Cannot deactivate the last active admin.")
    get_client().table("users").update({"is_active": is_active}).eq("id", user_id).execute()


def set_role(user_id: str, role: str) -> None:
    if role not in ("admin", "user"):
        raise ValueError("Role must be 'admin' or 'user'.")
    if role != "admin" and _is_last_active_admin(user_id):
        raise ValueError("Cannot demote the last active admin.")
    get_client().table("users").update({"role": role}).eq("id", user_id).execute()


def reset_password(user_id: str, new_password: str) -> None:
    if not new_password or len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    get_client().table("users").update(
        {"password_hash": hash_password(new_password)}
    ).eq("id", user_id).execute()


def delete_user(user_id: str) -> None:
    """Delete a user. Their assets/maintenance/agent_memory cascade-delete (FK)."""
    if _is_last_active_admin(user_id):
        raise ValueError("Cannot delete the last active admin.")
    get_client().table("users").delete().eq("id", user_id).execute()


def _is_last_active_admin(user_id: str) -> bool:
    """True if user_id is an active admin and the only one."""
    admins = (
        get_client()
        .table("users")
        .select("id")
        .eq("role", "admin")
        .eq("is_active", True)
        .execute()
        .data
    )
    admin_ids = {a["id"] for a in admins}
    return admin_ids == {user_id}


# ---------------------------------------------------------------------------
# First-run bootstrap
# ---------------------------------------------------------------------------

def bootstrap_admin() -> None:
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD if no users exist."""
    count = get_client().table("users").select("id", count="exact").execute().count or 0
    if count > 0:
        return
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        print(
            "No users found and ADMIN_EMAIL/ADMIN_PASSWORD not set — "
            "set them in .env to bootstrap the first admin account."
        )
        return
    create_user(email, password, role="admin")
    print(f"Bootstrapped admin account: {email.strip().lower()}")
