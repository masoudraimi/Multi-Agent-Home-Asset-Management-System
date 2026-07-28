"""Compliance-grade audit log with Pydantic schema validation.

The new audit target for LangGraph nodes and any Phase-1+ code. The legacy
`core.observability.audit_log` stays put during the migration; both write to
`data/audit.log` so downstream tooling only reads one file.

Every audit event is immutable — corrections are separate `correction`
events referencing a prior `request_id`. Free-text fields (e.g. asset notes)
should be hashed via `hash_free_text` before being placed in `payload` to
avoid retaining PII.

Usage:
    from core.audit import audit, hash_free_text
    audit(
        "asset_deleted",
        actor="agent",
        request_id=req_id,
        trace_id=trace_id,
        user_id=user_id,
        agent="asset",
        payload={"asset_id": 4, "name_hash": hash_free_text("House Gutters")},
    )

Rotation is not automatic — call `rotate()` weekly (via cron or a scheduled
LangGraph job) to compress `data/audit.log` into `data/audit-YYYY-WW.log.gz`.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.logging import get_logger

log = get_logger(__name__)

_APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")

AuditActor = Literal["user", "system", "agent"]

# Whitelist. Events not listed here are dropped with a WARN log — this
# prevents the audit trail from becoming a general-purpose log dump.
AUDIT_EVENT_TYPES: frozenset[str] = frozenset({
    # Approval flow
    "approval_requested",
    "approval_confirmed",
    "approval_cancelled",
    "approval_timeout",
    # Asset mutations
    "asset_created",
    "asset_updated",
    "asset_deleted",
    "asset_delete_failed",
    # Maintenance mutations
    "maintenance_logged",
    # Auth
    "user_login",
    "user_logout",
    "user_created",
    "user_role_changed",
    "user_activation_changed",
    # Guardrails
    "guardrail_pii_blocked",
    "guardrail_injection_blocked",
    # Budget
    "budget_exhausted",
    # Corrections reference a prior event's request_id
    "correction",
})


class AuditEvent(BaseModel):
    ts: str                             # ISO-8601 UTC with millisecond precision, Z-suffixed
    request_id: str
    trace_id: str | None = None
    user_id: str | None = None
    agent: str | None = None
    event_type: str
    actor: AuditActor
    payload: dict[str, Any] = Field(default_factory=dict)
    app_version: str = _APP_VERSION
    references: str | None = None       # request_id of a prior event this one corrects


# ── Redaction helpers ──────────────────────────────────────────────────────
def hash_free_text(value: str) -> str:
    """Return a stable short hash of free text. Use for asset names, notes, etc.

    Prefix keeps the hash type explicit so future migrations can detect them.
    """
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


# ── Writer ─────────────────────────────────────────────────────────────────
_write_lock = Lock()


def _audit_path() -> Path:
    return Path(__file__).parent.parent / "data" / "audit.log"


def audit(
    event_type: str,
    *,
    request_id: str,
    actor: AuditActor = "system",
    trace_id: str | None = None,
    user_id: str | None = None,
    agent: str | None = None,
    payload: dict[str, Any] | None = None,
    references: str | None = None,
) -> None:
    """Append a validated event to `data/audit.log`. Never raises to caller."""
    if event_type not in AUDIT_EVENT_TYPES:
        log.warning("audit_dropped_unknown_event", event_type=event_type, request_id=request_id)
        return
    try:
        event = AuditEvent(
            ts=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            request_id=request_id,
            trace_id=trace_id,
            user_id=user_id,
            agent=agent,
            event_type=event_type,
            actor=actor,
            payload=payload or {},
            references=references,
        )
        path = _audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
    except Exception:
        # Audit must never crash the app. Log with full context and continue.
        log.exception("audit_write_failed", event_type=event_type, request_id=request_id)


# ── Rotation ───────────────────────────────────────────────────────────────
def rotate() -> Path | None:
    """Compress the current audit log to `data/audit-YYYY-WW.log.gz`.

    Returns the archive path, or None if the log is empty / missing. Runs
    under the same lock as writes to avoid a torn compression.
    """
    current = _audit_path()
    if not current.exists() or current.stat().st_size == 0:
        return None
    now = datetime.now(timezone.utc)
    archive = current.parent / f"audit-{now:%Y-W%V}.log.gz"
    with _write_lock:
        with open(current, "rb") as src, gzip.open(archive, "wb") as dst:
            shutil.copyfileobj(src, dst)
        current.unlink()
    log.info("audit_rotated", archive=str(archive))
    return archive


# ── Reader (for tests + admin UI drill-down) ───────────────────────────────
def recent_events(limit: int = 50, event_type: str | None = None) -> list[dict]:
    """Read the tail of the audit log. Best-effort — corrupted lines are skipped."""
    import json as _json

    path = _audit_path()
    if not path.exists():
        return []
    lines: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lines.append(line)

    out: list[dict] = []
    for line in reversed(lines):
        try:
            obj = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        if event_type and obj.get("event_type") != event_type:
            continue
        out.append(obj)
        if len(out) >= limit:
            break
    return out
