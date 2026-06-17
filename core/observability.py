"""OpenTelemetry observability: in-memory span exporter + JSONL audit log."""

from __future__ import annotations

import json
import time
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_AUDIT_LOG_PATH = Path(__file__).parent.parent / "data" / "audit.jsonl"

_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
trace.set_tracer_provider(_provider)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def get_recent_spans(limit: int = 50) -> list[dict]:
    """Return the most recent completed spans as plain dicts for the Streamlit tab."""
    finished = _exporter.get_finished_spans()
    result = []
    for s in reversed(list(finished)[-limit:]):
        result.append({
            "name": s.name,
            "agent": s.attributes.get("agent_name", "") if s.attributes else "",
            "start_ms": s.start_time // 1_000_000,
            "duration_ms": (s.end_time - s.start_time) // 1_000_000,
            "status": s.status.status_code.name,
            "attributes": dict(s.attributes or {}),
        })
    return result


def audit_log(event_type: str, data: dict) -> None:
    """Append a JSONL line to the audit log file."""
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"ts": time.time(), "event": event_type, **data})
        with open(_AUDIT_LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
