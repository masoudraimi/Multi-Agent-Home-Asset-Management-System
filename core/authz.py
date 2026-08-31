"""Tool-level authorization: gate individual tool calls by the caller's role.

Role travels via `core.session`'s ContextVar (set alongside `user_id`, never
as an LLM tool argument) — the same non-spoofable pattern already used for
per-user data isolation. This is the seam for admin-only tools; today every
authenticated role in `("user", "admin")` may call `delete_asset` since
ownership (via `user_id` scoping in `tools/db.py`) is the real access
boundary for asset mutations, not role. The decorator still proves the
enforcement + audit path end-to-end so it's ready when an actually
role-restricted tool is added.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from structlog.contextvars import get_contextvars

from core.audit import audit
from core.logging import get_logger
from core.session import get_current_user_role_or_none

log = get_logger(__name__)


class AuthorizationError(RuntimeError):
    """Raised when the current user's role isn't permitted to call a tool."""


def require_role(*allowed_roles: str) -> Callable:
    """Decorator for @tool-wrapped functions. Reads the role from
    `core.session` — never a tool argument — and raises `AuthorizationError`
    (which LangGraph's ToolNode turns into an error ToolMessage fed back to
    the LLM, not a crash) if it isn't in `allowed_roles`.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            role = get_current_user_role_or_none()
            if role not in allowed_roles:
                ctx = get_contextvars()
                log.warning(
                    "tool_authorization_denied", tool=fn.__name__, role=role, required=list(allowed_roles),
                )
                audit(
                    "tool_authorization_denied",
                    request_id=ctx.get("request_id", ""),
                    actor="agent",
                    user_id=ctx.get("user_id"),
                    agent=ctx.get("agent"),
                    payload={"tool": fn.__name__, "role": role, "required_roles": list(allowed_roles)},
                )
                raise AuthorizationError(
                    f"Role '{role}' is not permitted to call '{fn.__name__}'. "
                    f"Requires one of: {', '.join(allowed_roles)}."
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator
