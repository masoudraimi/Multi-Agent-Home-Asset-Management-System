"""Migrate semantic_memory from the legacy JSON-blob `embedding` column to
the pgvector `embedding_vec` column added by db/neon.py and db/supabase.py.

No real production content exists yet — every row in `semantic_memory` today
is reproducible from `core/schema.py` (plant care + checklist data) via
`knowledge/rag/indexer.py`, and pre-pgvector rows are typically stub-embedded
(meaningless hash vectors) anyway. So the correct migration here is not a
cast of the old blob into the new column — it's a clear + re-index with a
real embedding backend.

Run with:
  uv run python scripts/migrate_pgvector.py             # dry-run: report only
  uv run python scripts/migrate_pgvector.py --apply     # clear + re-index
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from core.memory.semantic import SemanticMemory, _STUB_MODEL
from db import get_provider
from knowledge.rag.indexer import index_all

_AGENTS = ("asset", "maintenance", "insights")


def _report() -> None:
    provider = get_provider()
    for agent in _AGENTS:
        total = provider.semantic_count(agent)
        print(f"{agent}: {total} row(s) in semantic_memory")
    import os
    if not os.environ.get("VOYAGE_API_KEY", "").strip():
        print(
            "\nVOYAGE_API_KEY is not set — re-indexing would embed with the "
            f"hash stub ({_STUB_MODEL}), which carries no semantic meaning. "
            "Set VOYAGE_API_KEY before running --apply for a real migration."
        )


def _apply() -> None:
    for agent in _AGENTS:
        SemanticMemory(agent).clear()
    print("Cleared semantic_memory for:", ", ".join(_AGENTS))
    counts = index_all(force=True)
    print(f"Re-indexed with pgvector: {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Clear and re-index (default is dry-run report)")
    args = parser.parse_args()

    if args.apply:
        _apply()
    else:
        _report()
        print("\nDry run only. Re-run with --apply to clear and re-index.")


if __name__ == "__main__":
    main()
