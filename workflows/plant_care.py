"""Backward-compatibility shim. Logic lives in agents/maintenance/workflows/plant_care.py."""

from agents.maintenance.workflows.plant_care import (  # noqa: F401
    get_plant_care_schedule,
)

__all__ = ["get_plant_care_schedule"]
