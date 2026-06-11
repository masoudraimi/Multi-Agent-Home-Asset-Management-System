"""Backward-compatibility shim. Logic lives in agents/maintenance/workflows/telegram.py."""

from agents.maintenance.workflows.telegram import (  # noqa: F401
    build_monthly_digest,
    send_telegram_message,
)

__all__ = ["build_monthly_digest", "send_telegram_message"]
