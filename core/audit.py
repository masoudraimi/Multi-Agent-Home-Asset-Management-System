"""Compliance-grade, tamper-evident audit log with Pydantic schema validation.

The single writer for `data/audit.log` — the legacy `core.observability.audit_log`
JSONL shim (unchained, incompatible with the hash chain below) has been
migrated away from and removed; every caller now goes through `audit()` here.

Every audit event is immutable — corrections are separate `correction`
events referencing a prior `request_id`. Free-text fields (e.g. asset notes)
should be hashed via `hash_free_text` before being placed in `payload` to
avoid retaining PII.

Tamper evidence: every entry embeds `prev_hash` (the previous entry's
`entry_hash`) and its own `entry_hash` = sha256(prev_hash + canonical_json(
entry minus entry_hash)). Editing or deleting a line breaks the chain from
that point forward; `verify_chain()` detects the first broken link. This is
filesystem-only (no external service) — a real, verifiable local guarantee,
not a distributed-ledger claim.

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
Rotation persists the chain's last hash to a sidecar file so verification
continues seamlessly across the rotation boundary.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.logging import get_logger

log = get_logger(__name__)

_APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")

AuditActor = Literal["user", "system", "agent"]

GENESIS_HASH = "0" * 64
_CHAIN_STATE_FILENAME = "audit-chain-state.json"

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
    "asset_create_failed",
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
    # Governance
    "budget_exhausted",
    "rate_limit_exceeded",
    "tool_authorization_denied",
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
    prev_hash: str = GENESIS_HASH
    entry_hash: str = ""


# ── Redaction helpers ──────────────────────────────────────────────────────
def hash_free_text(value: str) -> str:
    """Return a stable short hash of free text. Use for asset names, notes, etc.

    Prefix keeps the hash type explicit so future migrations can detect them.
    """
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _canonical_json(d: dict) -> str:
    """Stable serialization used on both the write side and verify side —
    field order and separators must match exactly for hashes to compare."""
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def _entry_hash(event_dict_without_hash: dict) -> str:
    return hashlib.sha256(_canonical_json(event_dict_without_hash).encode("utf-8")).hexdigest()


# ── Writer ─────────────────────────────────────────────────────────────────
_write_lock = Lock()
_last_hash_cache: str | None = None  # populated lazily; guarded by _write_lock


def _audit_path() -> Path:
    return Path(__file__).parent.parent / "data" / "audit.log"


def _chain_state_path() -> Path:
    return _audit_path().parent / _CHAIN_STATE_FILENAME


def _read_chain_state() -> dict | None:
    p = _chain_state_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_chain_state(state: dict) -> None:
    p = _chain_state_path()
    try:
        p.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        log.exception("audit_chain_state_write_failed")


def _last_line_of(path: Path) -> str | None:
    last: str | None = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last = line
    return last


def _get_last_hash_locked() -> str:
    """Must be called while holding `_write_lock`. Resolves the chain's tip:
    the in-process cache, else the live log's last entry, else the rotation
    sidecar's last hash (so a fresh file after rotation chains correctly),
    else genesis."""
    global _last_hash_cache
    if _last_hash_cache is not None:
        return _last_hash_cache

    path = _audit_path()
    if path.exists() and path.stat().st_size > 0:
        last_line = _last_line_of(path)
        if last_line:
            try:
                obj = json.loads(last_line)
                _last_hash_cache = obj.get("entry_hash") or GENESIS_HASH
                return _last_hash_cache
            except json.JSONDecodeError:
                pass

    state = _read_chain_state()
    _last_hash_cache = (state or {}).get("last_hash", GENESIS_HASH)
    return _last_hash_cache


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
    """Append a validated, hash-chained event to `data/audit.log`. Never raises."""
    if event_type not in AUDIT_EVENT_TYPES:
        log.warning("audit_dropped_unknown_event", event_type=event_type, request_id=request_id)
        return
    global _last_hash_cache
    try:
        with _write_lock:
            prev_hash = _get_last_hash_locked()
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
                prev_hash=prev_hash,
            )
            entry_hash = _entry_hash(event.model_dump(exclude={"entry_hash"}))
            event.entry_hash = entry_hash

            path = _audit_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
            _last_hash_cache = entry_hash
    except Exception:
        # Audit must never crash the app. Log with full context and continue.
        log.exception("audit_write_failed", event_type=event_type, request_id=request_id)


# ── Rotation ───────────────────────────────────────────────────────────────
def rotate() -> Path | None:
    """Compress the current audit log to `data/audit-YYYY-WW.log.gz`.

    Returns the archive path, or None if the log is empty / missing. Runs
    under the same lock as writes to avoid a torn compression. Persists the
    chain's tip hash to a sidecar file so the next file (post-rotation)
    chains from the archived file's last entry rather than restarting at
    genesis.
    """
    current = _audit_path()
    if not current.exists() or current.stat().st_size == 0:
        return None
    now = datetime.now(timezone.utc)
    archive = current.parent / f"audit-{now:%Y-W%V}.log.gz"
    with _write_lock:
        last_hash = _get_last_hash_locked()
        with open(current, "rb") as src, gzip.open(archive, "wb") as dst:
            shutil.copyfileobj(src, dst)
        current.unlink()
        _write_chain_state({"last_hash": last_hash, "last_archive": str(archive)})
        # Cache already holds `last_hash`; keep it so writes right after
        # rotation chain correctly without re-reading the (now-empty) file.
    log.info("audit_rotated", archive=str(archive))
    return archive


# ── Verification ───────────────────────────────────────────────────────────
@dataclass
class ChainVerificationResult:
    ok: bool
    total_entries: int
    first_broken_line: int | None
    reason: str | None  # "hash_mismatch" | "invalid_json" | "missing_field" | "prev_hash_mismatch" | None


def verify_chain(path: Path | None = None) -> ChainVerificationResult:
    """Re-derive each entry's hash from its own payload + the previous
    entry's recorded hash, and check `prev_hash` linkage. Pure function, no
    side effects — stops at the first broken link and reports its line
    number. When verifying the live log (the default `path`), the chain's
    expected starting point comes from the rotation sidecar (if any) rather
    than genesis, so verification is correct across rotation boundaries.
    """
    target = path or _audit_path()
    if not target.exists():
        return ChainVerificationResult(ok=True, total_entries=0, first_broken_line=None, reason=None)

    if path is None:
        state = _read_chain_state()
        expected_prev = (state or {}).get("last_hash", GENESIS_HASH)
    else:
        expected_prev = GENESIS_HASH

    total = 0
    with open(target, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            total += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                return ChainVerificationResult(False, total, lineno, "invalid_json")
            if "entry_hash" not in obj or "prev_hash" not in obj:
                return ChainVerificationResult(False, total, lineno, "missing_field")
            if obj["prev_hash"] != expected_prev:
                return ChainVerificationResult(False, total, lineno, "prev_hash_mismatch")
            claimed = obj["entry_hash"]
            recomputed = _entry_hash({k: v for k, v in obj.items() if k != "entry_hash"})
            if recomputed != claimed:
                return ChainVerificationResult(False, total, lineno, "hash_mismatch")
            expected_prev = claimed
    return ChainVerificationResult(True, total, None, None)


# ── Reader (for tests + admin UI drill-down) ───────────────────────────────
def recent_events(limit: int = 50, event_type: str | None = None) -> list[dict]:
    """Read the tail of the audit log. Best-effort — corrupted lines are skipped."""
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
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event_type and obj.get("event_type") != event_type:
            continue
        out.append(obj)
        if len(out) >= limit:
            break
    return out
