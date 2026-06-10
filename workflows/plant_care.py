"""Workflow: look up a plant asset and generate a species-specific care schedule."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "home_assets.db"
PLANT_CARE_PATH = Path(__file__).parent.parent / "data" / "plant_care.json"

_CARE_DATA: dict | None = None


def _load_care_data() -> dict:
    global _CARE_DATA
    if _CARE_DATA is None:
        _CARE_DATA = json.loads(PLANT_CARE_PATH.read_text())
    return _CARE_DATA


def _fuzzy_match(species: str, care_data: dict) -> str:
    """Find the best matching key in care_data for the given species string."""
    if not species:
        return "default"
    s = species.lower().strip()
    for key in care_data:
        if key == "default":
            continue
        if key in s or s in key:
            return key
        # word-level match
        key_words = set(key.split())
        species_words = set(s.split())
        if key_words & species_words:
            return key
    return "default"


def get_plant_care_schedule(asset_id: int) -> dict:
    """Generate a care schedule for a plant/tree asset based on its species."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    asset = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if not asset:
        conn.close()
        return {"error": f"No asset found with id {asset_id}"}

    asset_dict = dict(asset)
    if asset_dict.get("category") != "plants_trees":
        conn.close()
        return {
            "error": f"Asset '{asset_dict['name']}' is not in the plants_trees category",
            "category": asset_dict.get("category"),
        }

    # Get last maintenance tasks for this asset
    last_tasks = {}
    rows = conn.execute(
        """SELECT task_name, MAX(completed_date) as last_done
           FROM maintenance_tasks WHERE asset_id = ?
           GROUP BY task_name""",
        (asset_id,),
    ).fetchall()
    conn.close()

    for row in rows:
        if row["last_done"]:
            last_tasks[row["task_name"].lower()] = row["last_done"]

    species = asset_dict.get("plant_species") or ""
    care_data = _load_care_data()
    matched_key = _fuzzy_match(species, care_data)
    schedule_template = care_data.get(matched_key, care_data["default"])

    today = date.today()
    planting_date = asset_dict.get("planting_date")
    size = asset_dict.get("plant_size", "unknown")

    tasks = []
    for task_name, config in schedule_template.items():
        interval = config["interval_days"]
        notes = config["notes"]

        # Find last completed date for this task type
        last_done = None
        for key in last_tasks:
            if task_name.replace("_", " ") in key or key in task_name.replace("_", " "):
                last_done = last_tasks[key]
                break

        if last_done:
            next_due = (date.fromisoformat(last_done) + timedelta(days=interval)).isoformat()
        elif planting_date:
            next_due = (date.fromisoformat(planting_date) + timedelta(days=interval)).isoformat()
        else:
            next_due = (today + timedelta(days=7)).isoformat()

        days_until = (date.fromisoformat(next_due) - today).days
        urgency = "overdue" if days_until < 0 else "due_soon" if days_until <= 14 else "upcoming"

        tasks.append({
            "task": task_name.replace("_", " "),
            "next_due": next_due,
            "days_until_due": days_until,
            "urgency": urgency,
            "interval_days": interval,
            "notes": notes,
            "last_completed": last_done,
        })

    tasks.sort(key=lambda t: t["days_until_due"])

    return {
        "asset_id": asset_id,
        "asset_name": asset_dict["name"],
        "species": species or "unknown",
        "matched_template": matched_key,
        "size": size,
        "location": asset_dict.get("location", ""),
        "care_tasks": tasks,
    }
