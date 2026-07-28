"""Structured JSON logging with correlation IDs and PII redaction.

Every log line carries whatever correlation IDs are bound to the current async
task (request_id, thread_id, trace_id, user_id), and any value that looks like
a secret or PII pattern is redacted before serialisation.

Callers:
    from core.logging import get_logger, bind_correlation
    log = get_logger(__name__)

    bind_correlation(request_id=req_id, user_id=uid)
    log.info("tool_called", tool="add_asset", args_len=len(args_json))

Logging must never crash the app — structlog itself is safe, but wrap
`configure()` in try/except at app entry if you're paranoid about start-up
errors leaking through.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars

# ── Correlation ID binding ─────────────────────────────────────────────────
_CORRELATION_KEYS = ("request_id", "thread_id", "trace_id", "user_id", "session_id", "agent")


def bind_correlation(**kwargs: Any) -> None:
    """Attach correlation IDs to the current async task.

    All subsequent log lines from this task (and its awaited children) inherit
    them via structlog's contextvars integration. Pass None for a key to leave
    it unchanged; only non-None values overwrite.
    """
    to_bind = {k: v for k, v in kwargs.items() if v is not None and k in _CORRELATION_KEYS}
    if to_bind:
        bind_contextvars(**to_bind)


def clear_correlation() -> None:
    """Reset all correlation IDs. Call at end of a request scope."""
    clear_contextvars()


# ── Redaction ──────────────────────────────────────────────────────────────
_SENSITIVE_KEY = re.compile(r"(?i)(api[_-]?key|token|password|secret|authorization|bearer)")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CC = re.compile(r"\b(?:\d[ -]?){13,16}\b")
_REDACT = "***REDACTED***"


def _redact_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(event_dict.items()):
        if _SENSITIVE_KEY.search(key):
            event_dict[key] = _REDACT
        elif isinstance(value, str):
            if _SSN.search(value):
                value = _SSN.sub(_REDACT, value)
            if _CC.search(value):
                value = _CC.sub(_REDACT, value)
            event_dict[key] = value
    return event_dict


# ── Configuration ──────────────────────────────────────────────────────────
def configure(json_output: bool | None = None, level: str | None = None) -> None:
    """Wire up structlog. JSON in prod, coloured console in dev.

    json_output: force JSON on/off. If None, uses APP_ENV=prod → JSON.
    level:       LOG_LEVEL env var, default INFO.
    """
    if json_output is None:
        json_output = os.environ.get("APP_ENV", "dev").lower() == "prod"
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, level, logging.INFO)

    # Route stdlib logging through the same handler so third-party libs
    # (uvicorn, langchain, httpx) inherit correlation IDs and formatting.
    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        stream=sys.stdout,
        force=True,
    )

    processors: list[Any] = [
        merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_processor,
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Namespaced logger. Use `name=__name__` in each module."""
    return structlog.get_logger(name)


# Configure eagerly on first import so early logs (before app startup runs
# configure() explicitly) still land in the same format. Safe to call
# configure() again to reconfigure at any point.
configure()
