"""Index schema data into semantic memory for RAG retrieval.

Run once at startup (or when schema files change) to populate semantic memory.
"""

from __future__ import annotations

from pathlib import Path

from core.memory.semantic import SemanticMemory
from db import get_provider
from knowledge.rag.ingest import ingest_document
from schema import get_checklist, get_plant_care

_SAMPLE_DOCS_DIR = Path(__file__).parent / "sample_docs"


def is_indexed(agent_name: str) -> bool:
    """Return True if semantic memory for this agent already has entries."""
    return get_provider().semantic_count(agent_name) > 0


def index_plant_care() -> int:
    """Index plant species care schedules into maintenance agent's semantic memory."""
    mem = SemanticMemory("maintenance")
    plant_care = get_plant_care()
    count = 0
    for species, tasks in plant_care.items():
        if species == "default":
            continue
        task_parts = [
            f"{task_name.replace('_', ' ')}: every {cfg['interval_days']} days. {cfg['notes']}"
            for task_name, cfg in tasks.items()
        ]
        text = f"Plant species: {species}. Care tasks: " + "; ".join(task_parts)
        mem.store(text, metadata={"source": "plant_care", "species": species})
        count += 1
    return count


def index_checklist() -> int:
    """Index asset checklist into asset agent's semantic memory."""
    mem = SemanticMemory("asset")
    checklist = get_checklist()
    count = 0
    for category, items in checklist.items():
        for item in items:
            text = (
                f"{item['name']} ({category}): {item['reason']}. "
                f"Priority: {item['priority']}."
            )
            mem.store(text, metadata={"source": "checklist", "category": category, "priority": item["priority"]})
            count += 1
    return count


def index_sample_docs() -> int:
    """Ingest bundled long-form reference docs (chunked, cited) into the
    maintenance agent's semantic memory — demonstrates the real chunked-RAG
    path (chunk -> embed -> pgvector index -> cited retrieval), not just
    single-line structured records."""
    total = 0
    for path in sorted(_SAMPLE_DOCS_DIR.glob("*.md")):
        total += ingest_document(
            agent_name="maintenance",
            source_name=path.stem,
            text=path.read_text(encoding="utf-8"),
            doc_type="manual",
        )
    return total


def index_all(force: bool = False) -> dict[str, int]:
    """Index all data sources. Skips if already indexed (unless force=True).

    `maintenance` already-indexed status is captured once, before either
    plant_care or sample_docs runs — both write into the same agent scope,
    so checking is_indexed("maintenance") a second time would see the first
    write and wrongly skip the second.
    """
    maintenance_already_indexed = is_indexed("maintenance")
    counts: dict[str, int] = {}
    counts["plant_care"] = index_plant_care() if (force or not maintenance_already_indexed) else 0
    counts["checklist"] = index_checklist() if (force or not is_indexed("asset")) else 0
    counts["sample_docs"] = index_sample_docs() if (force or not maintenance_already_indexed) else 0
    return counts


if __name__ == "__main__":
    result = index_all(force=True)
    print(f"Indexed: {result}")
