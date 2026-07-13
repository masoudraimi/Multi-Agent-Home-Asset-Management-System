"""Single source of truth for all asset schema data.

One typed Python module per category. Each module exposes a CategorySchema
(or PlantCategorySchema) instance validated at import time by Pydantic.

Public API - consumed by agents and workflows, never changed:
  get_questions(category)       -> list[str]
  get_checklist()               -> dict[str, list[dict]]
  get_plant_care()              -> dict[str, dict[str, dict]]
  get_maintenance_policies()    -> dict[str, dict[str, dict[str, dict]]]
"""

from __future__ import annotations

from schema.models import CategorySchema, PlantCategorySchema  # noqa: F401 - re-exported
from schema.appliances import APPLIANCES
from schema.electrical import ELECTRICAL
from schema.exterior import EXTERIOR
from schema.garden import GARDEN
from schema.hvac import HVAC
from schema.other import OTHER
from schema.plants_trees import PLANTS_TREES
from schema.plumbing import PLUMBING
from schema.vehicle import VEHICLE

_REGISTRY: list[CategorySchema] = [
    APPLIANCES, HVAC, PLUMBING, ELECTRICAL,
    EXTERIOR, VEHICLE, GARDEN, PLANTS_TREES, OTHER,
]

_BY_KEY: dict[str, CategorySchema] = {
    "appliances": APPLIANCES,
    "hvac": HVAC,
    "plumbing": PLUMBING,
    "electrical": ELECTRICAL,
    "exterior": EXTERIOR,
    "vehicle": VEHICLE,
    "garden": GARDEN,
    "plants_trees": PLANTS_TREES,
    "other": OTHER,
}

# Aliases the codebase may pass in (e.g. from DB values or synonym mapping)
_ALIAS: dict[str, str] = {
    "HVAC": "hvac",
    "plants_trees": "plants_trees",
}


def _resolve(category: str) -> str:
    return _ALIAS.get(category, category.lower().replace(" ", "_"))


def get_questions(category: str) -> list[str]:
    """Return onboarding questions for a category."""
    return (_BY_KEY.get(_resolve(category)) or OTHER).onboarding_questions


def get_checklist() -> dict[str, list]:
    """Return checklist items grouped by category (original case), for gap analysis.

    Returns {category: [{"name": str, "priority": str, "reason": str}]}
    """
    return {
        s.category: [item.model_dump() for item in s.checklist]
        for s in _REGISTRY
        if s.checklist
    }


def get_plant_care() -> dict:
    """Return per-species care schedules.

    Returns {species: {task_name: {"interval_days": int, "notes": str}}}
    Mirrors the structure of the old plant_care.json.
    """
    return {
        species: {task: cfg.model_dump() for task, cfg in tasks.items()}
        for species, tasks in PLANTS_TREES.species_care.items()
    }


def get_maintenance_policies() -> dict:
    """Return maintenance policies keyed by lowercased category name.

    Returns {category_lower: {sub_type: {task: {"interval_days": int, "notes": str}}}}
    Mirrors the structure of the old maintenance_policies.yaml.
    """
    return {
        s.category.lower(): {
            sub_type: {task: cfg.model_dump() for task, cfg in tasks.items()}
            for sub_type, tasks in s.maintenance_schedules.items()
        }
        for s in _REGISTRY
        if s.maintenance_schedules
    }
