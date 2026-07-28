"""Trace inspector — look up a past turn by request_id.

Phase 1 version: reads the audit log to reconstruct what happened. Full
LangGraph checkpoint replay (`graph.get_state(config, checkpoint_id=...)`)
lands in Phase 2 once the persistent checkpointer is wired up.

Usage:
    python scripts/replay.py <request_id>
    python scripts/replay.py --list           # list recent audit entries
    python scripts/replay.py --list --limit=100
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure the project root is on sys.path when running from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.audit import recent_events  # noqa: E402
from core.logging import get_logger  # noqa: E402

log = get_logger(__name__)


def _print_event(event: dict[str, Any]) -> None:
    ts = event.get("ts") or event.get("timestamp") or "?"
    et = event.get("event_type") or event.get("event") or "?"
    rid = event.get("request_id") or "?"
    user = event.get("user_id") or event.get("actor") or "?"
    payload = event.get("payload") or {k: v for k, v in event.items()
                                       if k not in {"ts", "event_type", "event", "request_id",
                                                    "trace_id", "user_id", "agent", "actor",
                                                    "app_version", "references"}}
    print(f"  [{ts}] {et:32}  req={rid}  user={user}")
    if payload:
        pretty = json.dumps(payload, default=str)[:400]
        print(f"      payload: {pretty}")


def cmd_list(limit: int) -> int:
    events = recent_events(limit=limit)
    if not events:
        print("audit.log is empty (or no matching entries).")
        return 0
    print(f"most recent {len(events)} audit events (newest first):")
    for ev in events:
        _print_event(ev)
    return 0


def cmd_lookup(request_id: str) -> int:
    matches = [e for e in recent_events(limit=5000) if e.get("request_id") == request_id]
    if not matches:
        print(f"no audit entries found for request_id={request_id}")
        print("try: python scripts/replay.py --list  to see recent requests")
        return 1
    print(f"found {len(matches)} audit entries for request_id={request_id}:")
    for ev in matches:
        _print_event(ev)

    print()
    print("Note: LangGraph checkpoint replay lands in Phase 2. For now, use the")
    print("LangSmith / Langfuse UI (search by request_id metadata) for full trace.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a past agent turn.")
    parser.add_argument("request_id", nargs="?", help="request_id to look up")
    parser.add_argument("--list", action="store_true", help="list recent audit entries")
    parser.add_argument("--limit", type=int, default=25, help="how many entries to list")
    args = parser.parse_args()

    if args.list:
        return cmd_list(args.limit)
    if not args.request_id:
        parser.print_help()
        return 2
    return cmd_lookup(args.request_id)


if __name__ == "__main__":
    raise SystemExit(main())
