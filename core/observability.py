"""Legacy observability shim.

Historically this module owned an OpenTelemetry `InMemorySpanExporter` +
`get_tracer` factory + `audit_log` file writer. Post-migration:

  * Tracing → LangSmith / Langfuse (see `agents/orchestrator/dispatcher.py`
    which wraps the whole turn in a `@traceable` chain).
  * Structured logs → `core.logging` (structlog JSON).
  * Metrics → `core.metrics` (Prometheus).
  * Audit → `core.audit` (Pydantic-validated JSONL with rotation).

`audit_log()` is kept as a thin forwarding shim so pre-migration callers
(currently `tools/db.py` for `asset_added` / `asset_deleted` legacy events)
keep working during the CLI path. New code should call `core.audit.audit`
directly for its typed schema and event-type whitelist.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any

from core.logging import get_logger

log = get_logger(__name__)

_AUDIT_LOG_PATH = Path(__file__).parent.parent / "data" / "audit.log"
_write_lock = Lock()


def audit_log(event_type: str, data: dict[str, Any]) -> None:
    """Append a JSONL line to `data/audit.log` — legacy pre-migration format.

    Kept for tools/db.py callers still using the old `{"ts": epoch, "event":
    <name>, ...data}` shape. New code should use `core.audit.audit` instead.
    Never raises to caller — errors log and drop.
    """
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"ts": time.time(), "event": event_type, **data})
        with _write_lock, open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        log.exception("legacy_audit_write_failed", event_type=event_type)
