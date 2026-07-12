from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class MaintenanceTask(BaseModel):
    interval_days: int
    notes: str


class ChecklistItem(BaseModel):
    name: str
    priority: Literal["high", "medium", "low"]
    reason: str


class CategorySchema(BaseModel):
    category: str
    onboarding_questions: list[str]
    checklist: list[ChecklistItem] = []
    maintenance_schedules: dict[str, dict[str, MaintenanceTask]] = {}


class PlantCategorySchema(CategorySchema):
    """plants_trees only: per-species care tasks replace maintenance_schedules."""
    species_care: dict[str, dict[str, MaintenanceTask]] = {}
