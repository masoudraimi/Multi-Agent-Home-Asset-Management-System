"""Current-user propagation for per-user data isolation.

The logged-in user's id is carried in a ContextVar so that the data layer
(tools/db.py) and memory layers can scope every query without the user id ever
being passed as an LLM tool argument (which would be spoofable).

Propagation across providers:
  - claude_sdk / openrouter: tools run in-process. The ContextVar set in the
    Streamlit thread is copied into the asyncio task automatically.
  - claude_cli: tools run in a subprocess (tools/stdio_server.py). The id is
    passed via the HOME_ASSET_USER_ID env var and re-applied there at startup.
"""

from __future__ import annotations

import contextvars

USER_ID_ENV_VAR = "HOME_ASSET_USER_ID"

_current_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_user_id", default=None
)

# Mirrors _current_user_id: the role travels via ContextVar/server-set state,
# never as an LLM tool argument, so it can't be spoofed by prompt content.
_current_user_role: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_user_role", default=None
)


class NoCurrentUserError(RuntimeError):
    """Raised when a user-scoped operation runs with no authenticated user."""


def set_current_user(user_id: str | None) -> None:
    """Set the current user id for this context (call once per Streamlit rerun)."""
    _current_user_id.set(user_id)


def get_current_user_id() -> str:
    """Return the current user id, or raise if none is set.

    Use in the data layer where an authenticated user is required.
    """
    uid = _current_user_id.get()
    if not uid:
        raise NoCurrentUserError(
            "No authenticated user in context. set_current_user() must be called "
            "before any user-scoped database access."
        )
    return uid


def get_current_user_id_or_none() -> str | None:
    """Return the current user id or None (for best-effort / optional scoping)."""
    return _current_user_id.get()


def set_current_user_role(role: str | None) -> None:
    """Set the current user's role for this context (call alongside set_current_user)."""
    _current_user_role.set(role)


def get_current_user_role() -> str:
    """Return the current user role, or raise if none is set."""
    role = _current_user_role.get()
    if not role:
        raise NoCurrentUserError(
            "No authenticated user role in context. set_current_user_role() must be "
            "called before any role-scoped operation."
        )
    return role


def get_current_user_role_or_none() -> str | None:
    """Return the current user role or None (for best-effort / optional scoping)."""
    return _current_user_role.get()
