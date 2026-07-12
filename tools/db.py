"""Core CRUD functions for the home asset database.

These are plain Python functions — no decorator magic. The MCP server in
tools/mcp_server.py wraps them with the claude-agent-sdk tool decorator.

All DB operations delegate to the active provider via db.get_provider().
Session concern (current user) is resolved here, not inside the provider.
"""

from typing import Optional

from core.observability import audit_log
from core.session import get_current_user_id
from db import get_provider


# ---------------------------------------------------------------------------
# Core CRUD tools
# ---------------------------------------------------------------------------

def add_asset(
    name: str,
    category: str,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    serial: Optional[str] = None,
    purchase_date: Optional[str] = None,
    purchase_price: Optional[float] = None,
    warranty_expiry: Optional[str] = None,
    location: Optional[str] = None,
    notes: Optional[str] = None,
    plant_species: Optional[str] = None,
    plant_size: Optional[str] = None,
    planting_date: Optional[str] = None,
    plant_notes: Optional[str] = None,
) -> dict:
    """Register a new home asset in the database.

    name: Human-readable name, e.g. 'Bosch Dishwasher' or 'Lemon Tree'
    category: One of: appliances, HVAC, plumbing, electrical, exterior, vehicle, garden, plants_trees, other
    brand: Manufacturer brand name
    model: Model number or name
    serial: Serial number
    purchase_date: ISO date string YYYY-MM-DD
    purchase_price: Purchase price in dollars
    warranty_expiry: ISO date string YYYY-MM-DD when warranty expires
    location: Room or area, e.g. 'Kitchen', 'Back yard left corner'
    notes: Any additional notes
    plant_species: Species name for plants_trees category (e.g. 'lemon tree', 'agapanthus')
    plant_size: Size for plants: small, medium, large, or mature
    planting_date: ISO date when plant was planted
    plant_notes: Plant-specific care notes
    """
    try:
        result = get_provider().add_asset(
            name=name, category=category, brand=brand, model=model, serial=serial,
            purchase_date=purchase_date, purchase_price=purchase_price,
            warranty_expiry=warranty_expiry, location=location, notes=notes,
            plant_species=plant_species, plant_size=plant_size,
            planting_date=planting_date, plant_notes=plant_notes,
            user_id=get_current_user_id(),
        )
        audit_log("asset_added", {"name": name, "category": category, "result": result})
        return result
    except Exception as exc:
        audit_log("asset_add_failed", {"name": name, "category": category, "error": str(exc)})
        raise


def list_assets(category: Optional[str] = None) -> dict:
    """List all home assets, optionally filtered by category.

    category: Optional filter — one of: appliances, HVAC, plumbing, electrical, exterior, vehicle, garden, plants_trees, other
    """
    return get_provider().list_assets(get_current_user_id(), category)


def search_assets(query: str) -> dict:
    """Search for assets by name, brand, model, species, or notes.

    query: Search term to match against asset fields
    """
    return get_provider().search_assets(get_current_user_id(), query)


def log_maintenance(
    asset_id: int,
    task_name: str,
    completed_date: Optional[str] = None,
    cost: Optional[float] = None,
    notes: Optional[str] = None,
    next_due_date: Optional[str] = None,
    interval_days: Optional[int] = None,
) -> dict:
    """Record a completed or scheduled maintenance task for an asset.

    asset_id: ID of the asset
    task_name: Description of the task, e.g. 'Filter replacement'
    completed_date: ISO date YYYY-MM-DD when done (defaults to today)
    cost: Cost in dollars
    notes: Notes about the work
    next_due_date: ISO date when this task is next due
    interval_days: Recurring interval in days
    """
    return get_provider().log_maintenance(
        user_id=get_current_user_id(),
        asset_id=asset_id,
        task_name=task_name,
        completed_date=completed_date,
        cost=cost,
        notes=notes,
        next_due_date=next_due_date,
        interval_days=interval_days,
    )


def get_upcoming_maintenance(days_ahead: int = 30) -> dict:
    """Get all maintenance tasks due within the next N days, including overdue ones.

    days_ahead: Number of days to look ahead (default 30)
    """
    return get_provider().get_upcoming_maintenance(get_current_user_id(), days_ahead)


def get_asset_history(asset_id: int) -> dict:
    """Get the full maintenance history and total cost for a specific asset.

    asset_id: ID of the asset
    """
    return get_provider().get_asset_history(get_current_user_id(), asset_id)


def update_asset(
    asset_id: int,
    name: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    serial: Optional[str] = None,
    purchase_date: Optional[str] = None,
    purchase_price: Optional[float] = None,
    warranty_expiry: Optional[str] = None,
    location: Optional[str] = None,
    notes: Optional[str] = None,
    plant_species: Optional[str] = None,
    plant_size: Optional[str] = None,
    planting_date: Optional[str] = None,
    plant_notes: Optional[str] = None,
) -> dict:
    """Update one or more fields on an existing asset.

    asset_id: ID of the asset to update
    name: New name
    category: New category
    brand: New brand
    model: New model
    serial: New serial number
    purchase_date: New purchase date YYYY-MM-DD
    purchase_price: New purchase price
    warranty_expiry: New warranty expiry YYYY-MM-DD
    location: New location
    notes: New notes
    plant_species: Species name (plants_trees only)
    plant_size: Size: small, medium, large, mature
    planting_date: Date planted YYYY-MM-DD
    plant_notes: Plant-specific notes
    """
    updates = {k: v for k, v in {
        "name": name, "category": category, "brand": brand, "model": model,
        "serial": serial, "purchase_date": purchase_date, "purchase_price": purchase_price,
        "warranty_expiry": warranty_expiry, "location": location, "notes": notes,
        "plant_species": plant_species, "plant_size": plant_size,
        "planting_date": planting_date, "plant_notes": plant_notes,
    }.items() if v is not None}

    if not updates:
        return {"status": "no_change"}

    return get_provider().update_asset(get_current_user_id(), asset_id, updates)


# ---------------------------------------------------------------------------
# Tools delegating to workflows
# ---------------------------------------------------------------------------

def get_onboarding_questions(asset_type: str) -> dict:
    """Get guided onboarding questions for a specific asset type.

    asset_type: The type or category of asset being added (e.g. 'appliances', 'plant', 'HVAC')
    """
    from workflows.onboarding import get_onboarding_questions as _fn
    return _fn(asset_type)


def review_asset_draft(draft_json: str) -> dict:
    """LLM-as-judge: review a partially-filled asset draft before saving.

    draft_json: JSON string of the asset fields collected so far
    """
    from workflows.onboarding import review_asset_draft as _fn
    return _fn(draft_json)


def get_plant_care_schedule(asset_id: int) -> dict:
    """Get a species-specific care schedule for a plant or tree asset.

    asset_id: ID of the plant/tree asset
    """
    from workflows.plant_care import get_plant_care_schedule as _fn
    return _fn(asset_id)


def suggest_missing_assets() -> dict:
    """Suggest commonly-missed home assets by comparing your database to a comprehensive checklist."""
    from workflows.suggestions import suggest_missing_assets as _fn
    return _fn()
