"""Plant care workflow: species-specific care schedule generation."""

from __future__ import annotations

from datetime import date, timedelta

from core.session import get_current_user_id
from db import get_provider
from schema import get_plant_care


def _load_care_data() -> dict:
    return get_plant_care()


def _fuzzy_match(species: str, care_data: dict) -> str:
    if not species:
        return "default"
    s = species.lower().strip()
    for key in care_data:
        if key == "default":
            continue
        if key in s or s in key:
            return key
        if set(key.split()) & set(s.split()):
            return key
    return "default"


def get_plant_care_schedule(asset_id: int) -> dict:
    """Generate a care schedule for a plant/tree asset based on its species."""
    uid = get_current_user_id()
    history = get_provider().get_asset_history(uid, asset_id)
    if history.get("status") == "error":
        return {"error": history["message"]}

    asset = history["asset"]
    if asset.get("category") != "plants_trees":
        return {
            "error": f"Asset '{asset['name']}' is not in the plants_trees category",
            "category": asset.get("category"),
        }

    task_rows = [t for t in history["history"] if t.get("completed_date")]

    last_tasks: dict[str, str] = {}
    for row in task_rows:
        key = row["task_name"].lower()
        if key not in last_tasks or row["completed_date"] > last_tasks[key]:
            last_tasks[key] = row["completed_date"]

    species = asset.get("plant_species") or ""
    care_data = _load_care_data()
    matched_key = _fuzzy_match(species, care_data)
    schedule_template = care_data.get(matched_key, care_data["default"])

    today = date.today()
    planting_date = asset.get("planting_date")
    size = asset.get("plant_size", "unknown")

    tasks = []
    for task_name, config in schedule_template.items():
        interval = config["interval_days"]
        notes = config["notes"]

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
        "asset_name": asset["name"],
        "species": species or "unknown",
        "matched_template": matched_key,
        "size": size,
        "location": asset.get("location", ""),
        "care_tasks": tasks,
    }
