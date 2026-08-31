"""Pydantic input schemas for every tool exposed to LangChain / LangGraph.

Single source of truth — imported by both `tools/langchain_tools.py`
(LangGraph path) and `tools/stdio_server.py` (Claude Code CLI / MCP path),
so the tool contract is single-sourced across both runtimes.

Kept flat + typed rather than dynamically generated so IDE navigation
and Pydantic strict-mode both work.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AddAssetInput(BaseModel):
    name: str
    category: str
    brand: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None
    warranty_expiry: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    plant_species: Optional[str] = None
    plant_size: Optional[str] = None
    planting_date: Optional[str] = None
    plant_notes: Optional[str] = None
    is_indoor: Optional[bool] = None
    rego_plate: Optional[str] = None
    odometer_km: Optional[int] = None
    next_service_km: Optional[int] = None


class ListAssetsInput(BaseModel):
    category: Optional[str] = None


class SearchAssetsInput(BaseModel):
    query: str


class LogMaintenanceInput(BaseModel):
    asset_id: int
    task_name: str
    completed_date: Optional[str] = None
    cost: Optional[float] = None
    notes: Optional[str] = None
    next_due_date: Optional[str] = None
    interval_days: Optional[int] = None


class GetUpcomingMaintenanceInput(BaseModel):
    days_ahead: int = 30


class GetAssetHistoryInput(BaseModel):
    asset_id: int


class UpdateAssetInput(BaseModel):
    asset_id: int
    name: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None
    warranty_expiry: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    plant_species: Optional[str] = None
    plant_size: Optional[str] = None
    planting_date: Optional[str] = None
    plant_notes: Optional[str] = None
    is_indoor: Optional[bool] = None
    rego_plate: Optional[str] = None
    odometer_km: Optional[int] = None
    next_service_km: Optional[int] = None


class DeleteAssetInput(BaseModel):
    asset_id: int


class ReviewDeleteAssetInput(BaseModel):
    asset_id: int


class GetOnboardingQuestionsInput(BaseModel):
    asset_type: str


class ReviewAssetDraftInput(BaseModel):
    draft_json: str


class GetPlantCareScheduleInput(BaseModel):
    asset_id: int


class SuggestMissingAssetsInput(BaseModel):
    pass


class GetExpiringWarrantiesInput(BaseModel):
    days_ahead: int = 90
