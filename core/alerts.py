"""Fire-and-forget alerts to Discord / Slack webhooks.

Configuration (any subset — nothing is required):
    DISCORD_WEBHOOK_URL   — real-time notifications go here
    SLACK_WEBHOOK_URL     — real-time notifications also mirror here
    ALERT_MIN_SEVERITY    — "info" | "warning" | "error" | "critical" (default "error")
    APP_ENV               — appended as a tag in the message

All calls are non-blocking best-effort — HTTP failures are logged (via
`core.logging`) but never raised. Every notification is also emitted as a
structured log line, so the webhook is decorative rather than authoritative.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx

from core.logging import get_logger

log = get_logger(__name__)

Severity = Literal["info", "warning", "error", "critical"]
_SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2, "critical": 3}

_DISCORD_COLOURS = {
    "info": 0x3B82F6,        # blue
    "warning": 0xF59E0B,     # amber
    "error": 0xEF4444,       # red
    "critical": 0x991B1B,    # dark red
}

_SLACK_ICONS = {
    "info": ":information_source:",
    "warning": ":warning:",
    "error": ":x:",
    "critical": ":rotating_light:",
}


def _min_severity() -> int:
    raw = os.environ.get("ALERT_MIN_SEVERITY", "error").lower()
    return _SEVERITY_ORDER.get(raw, 2)


def _env_tag() -> str:
    return os.environ.get("APP_ENV", "dev")


def notify(severity: Severity, message: str, context: dict[str, Any] | None = None) -> None:
    """Send an alert to configured channels. Never raises.

    severity: filtered by ALERT_MIN_SEVERITY (default 'error').
    message:  human-readable one-liner.
    context:  small dict of extra fields (keep it under a dozen keys).
    """
    ctx = dict(context or {})
    log.log(
        _stdlib_level(severity),
        "alert",
        severity=severity,
        message=message,
        **ctx,
    )
    if _SEVERITY_ORDER.get(severity, 0) < _min_severity():
        return

    payload_ctx = {"env": _env_tag(), **ctx}
    discord_url = os.environ.get("DISCORD_WEBHOOK_URL")
    slack_url = os.environ.get("SLACK_WEBHOOK_URL")
    if discord_url:
        _post(discord_url, _discord_payload(severity, message, payload_ctx), channel="discord")
    if slack_url:
        _post(slack_url, _slack_payload(severity, message, payload_ctx), channel="slack")


def _post(url: str, payload: dict[str, Any], *, channel: str) -> None:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
    except Exception:
        log.exception("alert_dispatch_failed", channel=channel)


def _discord_payload(severity: Severity, message: str, context: dict[str, Any]) -> dict[str, Any]:
    fields = [{"name": k, "value": str(v)[:1000], "inline": True} for k, v in context.items()]
    return {
        "username": "wisewombat-alerts",
        "embeds": [
            {
                "title": f"[{severity.upper()}] {message[:250]}",
                "color": _DISCORD_COLOURS[severity],
                "fields": fields,
            }
        ],
    }


def _slack_payload(severity: Severity, message: str, context: dict[str, Any]) -> dict[str, Any]:
    icon = _SLACK_ICONS[severity]
    ctx_lines = "\n".join(f"• *{k}*: `{v}`" for k, v in context.items())
    return {
        "text": f"{icon} *[{severity.upper()}]* {message}\n{ctx_lines}",
    }


# ── stdlib logging bridge ─────────────────────────────────────────────────
def _stdlib_level(severity: Severity) -> int:
    import logging as _stdlib

    return {
        "info": _stdlib.INFO,
        "warning": _stdlib.WARNING,
        "error": _stdlib.ERROR,
        "critical": _stdlib.CRITICAL,
    }[severity]


# ── Convenience wrappers for the common triggers listed in the plan ──────
def alert_retry_storm(tool: str, provider: str, count: int, window_seconds: int) -> None:
    notify(
        "warning",
        f"retry storm on {tool}",
        context={"tool": tool, "provider": provider, "count": count, "window_s": window_seconds},
    )


def alert_budget_breach(user_id: str, agent: str, spent_usd: float, limit_usd: float) -> None:
    notify(
        "error",
        f"budget exceeded for {agent}",
        context={"user_id": user_id, "agent": agent, "spent_usd": spent_usd, "limit_usd": limit_usd},
    )


def alert_checkpoint_failure(saver: str, error: str) -> None:
    notify(
        "critical",
        "checkpoint write failed — potential data loss",
        context={"saver": saver, "error": error},
    )


def alert_agent_error(request_id: str, agent: str, error: str) -> None:
    notify(
        "error",
        f"agent error in {agent}",
        context={"request_id": request_id, "agent": agent, "error": error[:500]},
    )
