"""LangGraph checkpointer factory.

Picks the backend based on `CHECKPOINTER` env var:

    memory   (default) — in-process only, lost on restart. Fine for dev + tests.
    sqlite             — file-backed at data/checkpoints.sqlite. Survives reload.
    postgres           — DATABASE_URL, uses the app's Neon/Supabase Postgres.

Every graph in the app should use the same checkpointer instance so a single
thread_id maps to one checkpoint history regardless of which specialist runs.

The InMemorySaver is created eagerly at module import so imports stay cheap
in test environments. Non-memory backends are opened lazily and cached.
"""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from core.logging import get_logger
from core.metrics import emit_checkpoint_write

log = get_logger(__name__)

_CHECKPOINT_DB = Path(__file__).parent.parent / "data" / "checkpoints.sqlite"

_lock = Lock()
_cached: Any | None = None


def _build_sqlite_saver() -> Any:
    """Lazy-import + open a persistent SQLite checkpointer."""
    from langgraph.checkpoint.sqlite import SqliteSaver
    import sqlite3

    _CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False so LangGraph async workers can share the conn.
    conn = sqlite3.connect(str(_CHECKPOINT_DB), check_same_thread=False)
    log.info("checkpointer_sqlite_opened", path=str(_CHECKPOINT_DB))
    return SqliteSaver(conn)


def _build_postgres_saver() -> Any:
    """Lazy-import + open a Postgres checkpointer keyed on DATABASE_URL."""
    from langgraph.checkpoint.postgres import PostgresSaver

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("CHECKPOINTER=postgres requires DATABASE_URL")
    saver = PostgresSaver.from_conn_string(url)
    # First-time setup: ensure the checkpoint tables exist.
    saver.setup()
    log.info("checkpointer_postgres_opened")
    return saver


def get_checkpointer() -> Any:
    """Return the process-wide checkpointer, opening it on first use."""
    global _cached
    with _lock:
        if _cached is not None:
            return _cached
        backend = os.environ.get("CHECKPOINTER", "memory").lower()
        try:
            if backend == "sqlite":
                _cached = _build_sqlite_saver()
            elif backend == "postgres":
                _cached = _build_postgres_saver()
            else:
                _cached = InMemorySaver()
                log.info("checkpointer_memory_opened")
            emit_checkpoint_write(backend, "success")
        except Exception:
            log.exception("checkpointer_open_failed", backend=backend)
            emit_checkpoint_write(backend, "error")
            # Fallback to in-memory so the app still runs.
            _cached = InMemorySaver()
        return _cached


def reset_for_tests() -> None:
    """Drop the cached checkpointer. Only use in test fixtures."""
    global _cached
    with _lock:
        _cached = None
