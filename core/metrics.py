"""Prometheus metrics + a tiny in-memory ring buffer for the admin UI.

All emit_* helpers are safe to call from anywhere — no import-time DB or
network access, no exceptions surfaced to callers. Prometheus counters are
process-local; scrape `/metrics` (see `metrics_endpoint`) to ship them.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Iterable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# ── Prometheus metrics ─────────────────────────────────────────────────────
# Histogram buckets tuned for LLM turn characteristics: sub-second is rare
# (only if hitting cache), most turns land 2-20s, budget-blown turns >30s.
_TURN_BUCKETS = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0)
_COST_BUCKETS = (0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0)
_PENDING_BUCKETS = (5.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0)

TURN_DURATION = Histogram(
    "agent_turn_duration_seconds",
    "Wall-clock duration of a single agent turn (specialist subgraph invocation).",
    labelnames=("agent", "outcome", "provider"),
    buckets=_TURN_BUCKETS,
)

TURN_COST = Histogram(
    "agent_turn_cost_usd",
    "Estimated LLM cost of a single agent turn, in USD.",
    labelnames=("agent", "provider"),
    buckets=_COST_BUCKETS,
)

TOOL_CALLS = Counter(
    "agent_tool_calls_total",
    "Tool invocations. Outcome is one of: success, error, retry.",
    labelnames=("tool", "outcome"),
)

TOOL_RETRIES = Counter(
    "agent_tool_retry_total",
    "Retries of the same tool call. Reason is one of: rate_limit, timeout, provider_error, other.",
    labelnames=("tool", "provider", "reason"),
)

GUARDRAIL_BLOCKS = Counter(
    "agent_guardrail_blocks_total",
    "Guardrail activations. Type is one of: injection, pii, output_len.",
    labelnames=("type",),
)

INTERRUPT_PENDING = Histogram(
    "agent_interrupt_pending_seconds",
    "How long a human-in-the-loop interrupt waited before resume/cancel.",
    labelnames=("action_type",),
    buckets=_PENDING_BUCKETS,
)

BUDGET_BREACHES = Counter(
    "agent_budget_breaches_total",
    "Turns terminated because a budget limit was exceeded.",
    labelnames=("agent", "limit_type"),
)

CHECKPOINT_WRITES = Counter(
    "agent_checkpoint_writes_total",
    "LangGraph checkpointer writes. Outcome is one of: success, error.",
    labelnames=("saver", "outcome"),
)


# ── Ring buffer for the admin UI "Recent turns" panel ──────────────────────
@dataclass
class TurnSummary:
    ts: float                       # Unix time when the turn ended
    request_id: str
    user_id: str
    agent: str
    provider: str
    outcome: str                    # "success" | "budget" | "max_iter" | "guardrail" | "error"
    duration_s: float
    cost_usd: float
    tool_calls: int
    tokens_in: int
    tokens_out: int
    termination_reason: str | None = None
    trace_url: str | None = None    # LangSmith / Langfuse deep-link if available
    tags: list[str] = field(default_factory=list)


_MAX_BUFFER = 200
_recent_turns: deque[TurnSummary] = deque(maxlen=_MAX_BUFFER)
_buffer_lock = Lock()


def record_turn(summary: TurnSummary) -> None:
    """Emit Prometheus samples and push into the in-memory buffer.

    Call once per specialist subgraph exit, after the exit node has computed
    the outcome and totals.
    """
    TURN_DURATION.labels(agent=summary.agent, outcome=summary.outcome, provider=summary.provider).observe(summary.duration_s)
    TURN_COST.labels(agent=summary.agent, provider=summary.provider).observe(summary.cost_usd)
    with _buffer_lock:
        _recent_turns.append(summary)


def recent_turns(limit: int = 50) -> list[dict]:
    """Return the last N turns as plain dicts (safe for Reflex state serialisation)."""
    with _buffer_lock:
        items = list(_recent_turns)[-limit:]
    return [asdict(t) for t in reversed(items)]


# ── Convenience emitters ───────────────────────────────────────────────────
def emit_tool_call(tool: str, outcome: str) -> None:
    TOOL_CALLS.labels(tool=tool, outcome=outcome).inc()


def emit_tool_retry(tool: str, provider: str, reason: str) -> None:
    TOOL_RETRIES.labels(tool=tool, provider=provider, reason=reason).inc()


def emit_guardrail_block(type_: str) -> None:
    GUARDRAIL_BLOCKS.labels(type=type_).inc()


def emit_interrupt_resolved(action_type: str, pending_seconds: float) -> None:
    INTERRUPT_PENDING.labels(action_type=action_type).observe(pending_seconds)


def emit_budget_breach(agent: str, limit_type: str) -> None:
    BUDGET_BREACHES.labels(agent=agent, limit_type=limit_type).inc()


def emit_checkpoint_write(saver: str, outcome: str) -> None:
    CHECKPOINT_WRITES.labels(saver=saver, outcome=outcome).inc()


# ── Scrape endpoint helpers ────────────────────────────────────────────────
def metrics_endpoint() -> tuple[bytes, str]:
    """Return (body, content_type) for a Prometheus scrape endpoint.

    Wire into Reflex via a custom API route or into FastAPI directly:
        @app.get("/metrics")
        def metrics():
            body, ct = metrics_endpoint()
            return Response(body, media_type=ct)
    """
    return generate_latest(), CONTENT_TYPE_LATEST


# ── Turn timing helper ─────────────────────────────────────────────────────
class TurnTimer:
    """Context manager for measuring a turn's wall-clock duration.

    Usage:
        with TurnTimer() as t:
            ... run the subgraph ...
        record_turn(TurnSummary(duration_s=t.elapsed, ...))
    """

    def __enter__(self) -> "TurnTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        self._end = time.monotonic()

    @property
    def elapsed(self) -> float:
        end = getattr(self, "_end", None) or time.monotonic()
        return end - self._start
