from pydantic import BaseModel
from typing import Optional


class Asset(BaseModel):
    id: int
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
    created_at: str


class MaintenanceTask(BaseModel):
    id: int
    asset_id: int
    asset_name: str
    task_name: str
    scheduled_date: Optional[str] = None
    completed_date: Optional[str] = None
    cost: Optional[float] = None
    notes: Optional[str] = None
    next_due_date: Optional[str] = None
    interval_days: Optional[int] = None
    created_at: str


class UpcomingTask(BaseModel):
    asset_id: int
    asset_name: str
    task_name: str
    next_due_date: str
    days_until_due: int
    urgency: str  # "overdue", "due_soon", "upcoming"
    last_completed: Optional[str] = None
