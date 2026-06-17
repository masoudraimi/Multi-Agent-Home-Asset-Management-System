"""Index data/ JSON files into semantic memory for RAG retrieval.

Run once at startup (or when data files change) to populate semantic memory.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.memory.semantic import SemanticMemory

DATA_ROOT = Path(__file__).parent.parent.parent / "data"


def is_indexed(agent_name: str) -> bool:
    """Return True if semantic memory for this agent already has entries."""
    mem = SemanticMemory(agent_name)
    import sqlite3
    from core.memory.semantic import DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM semantic_memory WHERE agent_name=?", (agent_name,)
        ).fetchone()[0]
    return count > 0


def index_plant_care() -> int:
    """Index plant_care.json into maintenance agent's semantic memory."""
    mem = SemanticMemory("maintenance")
    plant_care_path = DATA_ROOT / "plant_care.json"
    if not plant_care_path.exists():
        return 0
    plant_care = json.loads(plant_care_path.read_text())
    count = 0
    for species, tasks in plant_care.items():
        if species == "default":
            continue
        task_parts = []
        for task_name, cfg in tasks.items():
            task_parts.append(
                f"{task_name.replace('_', ' ')}: every {cfg['interval_days']} days. {cfg['notes']}"
            )
        text = f"Plant species: {species}. Care tasks: " + "; ".join(task_parts)
        mem.store(text, metadata={"source": "plant_care", "species": species})
        count += 1
    return count


def index_checklist() -> int:
    """Index home_asset_checklist.json into asset agent's semantic memory."""
    mem = SemanticMemory("asset")
    checklist_path = DATA_ROOT / "home_asset_checklist.json"
    if not checklist_path.exists():
        return 0
    checklist = json.loads(checklist_path.read_text())
    count = 0
    for category, items in checklist.items():
        for item in items:
            text = (
                f"{item['name']} ({category}): {item['reason']}. "
                f"Priority: {item['priority']}."
            )
            mem.store(text, metadata={
                "source": "checklist",
                "category": category,
                "priority": item["priority"],
            })
            count += 1
    return count


def index_all(force: bool = False) -> dict[str, int]:
    """Index all data sources. Skips if already indexed (unless force=True)."""
    counts: dict[str, int] = {}

    if force or not is_indexed("maintenance"):
        counts["plant_care"] = index_plant_care()
    else:
        counts["plant_care"] = 0

    if force or not is_indexed("asset"):
        counts["checklist"] = index_checklist()
    else:
        counts["checklist"] = 0

    return counts


if __name__ == "__main__":
    result = index_all(force=True)
    print(f"Indexed: {result}")
