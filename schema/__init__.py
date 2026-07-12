"""Single source of truth for all asset schema data.

One YAML file per category. Each file contains:
  - onboarding_questions  (asked during asset creation)
  - checklist             (gap-analysis items with priority)
  - maintenance_schedules (policy-based service intervals)
  - species_care          (plants_trees only: per-species care tasks)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_SCHEMA_DIR = Path(__file__).parent

_FILES = [
    "appliances", "hvac", "plumbing", "electrical",
    "exterior", "vehicle", "garden", "plants_trees", "other",
]

# Maps any category alias the codebase may use to the schema filename.
_ALIAS: dict[str, str] = {
    "HVAC": "hvac",
    "plants_trees": "plants_trees",
}


@lru_cache(maxsize=None)
def _load(filename: str) -> dict:
    return yaml.safe_load((_SCHEMA_DIR / f"{filename}.yaml").read_text())


def _resolve(category: str) -> str:
    return _ALIAS.get(category, category.lower().replace(" ", "_"))


def get_questions(category: str) -> list[str]:
    """Return onboarding questions for a category."""
    filename = _resolve(category)
    try:
        return _load(filename).get("onboarding_questions", [])
    except FileNotFoundError:
        return _load("other").get("onboarding_questions", [])


def get_checklist() -> dict[str, list]:
    """Return checklist items grouped by category, for gap analysis."""
    result: dict[str, list] = {}
    for filename in _FILES:
        data = _load(filename)
        items = data.get("checklist") or []
        if items:
            result[data["category"]] = items
    return result


def get_plant_care() -> dict:
    """Return per-species care schedules (structure mirrors the old plant_care.json)."""
    return _load("plants_trees").get("species_care", {})


def get_maintenance_policies() -> dict:
    """Return maintenance policies in the same nested structure as the old YAML.

    Keys are lowercased category names so callers can look up by
    asset_category.lower().replace(' ', '_').
    """
    result: dict[str, dict] = {}
    for filename in _FILES:
        data = _load(filename)
        schedules = data.get("maintenance_schedules") or {}
        if schedules:
            result[data["category"].lower()] = schedules
    return result
