"""Verify the tamper-evident hash chain in data/audit.log.

Exits 0 and prints a summary if the chain is intact, exits 1 and reports the
first broken line otherwise. Point CI or an admin runbook at this.

Run with:
  uv run python scripts/verify_audit_log.py [path/to/audit.log]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.audit import verify_chain


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    result = verify_chain(path)

    if result.ok:
        print(f"OK — {result.total_entries} entr{'y' if result.total_entries == 1 else 'ies'} verified, chain intact.")
        sys.exit(0)

    print(
        f"TAMPERING DETECTED — chain broken at line {result.first_broken_line} "
        f"(reason: {result.reason}). {result.total_entries} entries scanned."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
