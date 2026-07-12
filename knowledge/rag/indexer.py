"""Index schema data into semantic memory for RAG retrieval.

Run once at startup (or when schema files change) to populate semantic memory.
"""

from __future__ import annotations

from core.memory.semantic import SemanticMemory
from db import get_provider
from schema import get_checklist, get_plant_care


def is_indexed(agent_name: str) -> bool:
    """Return True if semantic memory for this agent already has entries."""
    return len(get_provider().semantic_retrieve(agent_name)) > 0


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


def index_all(force: bool = False) -> dict[str, int]:
    """Index all data sources. Skips if already indexed (unless force=True)."""
    counts: dict[str, int] = {}
    counts["plant_care"] = index_plant_care() if (force or not is_indexed("maintenance")) else 0
    counts["checklist"] = index_checklist() if (force or not is_indexed("asset")) else 0
    return counts


if __name__ == "__main__":
    result = index_all(force=True)
    print(f"Indexed: {result}")
