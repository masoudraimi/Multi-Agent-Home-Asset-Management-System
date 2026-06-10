"""Core CRUD functions for the home asset database.

These are plain Python functions — no decorator magic. The MCP server in
tools/mcp_server.py wraps them with the claude-agent-sdk tool decorator.
"""

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "home_assets.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


# ---------------------------------------------------------------------------
# Core CRUD tools (7 original)
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
    now = datetime.now().isoformat()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO assets
               (name, category, brand, model, serial, purchase_date, purchase_price,
                warranty_expiry, location, notes, plant_species, plant_size,
                planting_date, plant_notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, category, brand, model, serial, purchase_date, purchase_price,
             warranty_expiry, location, notes, plant_species, plant_size,
             planting_date, plant_notes, now),
        )
        asset_id = cur.lastrowid
    return {"status": "created", "asset_id": asset_id, "name": name}


def list_assets(category: Optional[str] = None) -> dict:
    """List all home assets, optionally filtered by category.

    category: Optional filter — one of: appliances, HVAC, plumbing, electrical, exterior, vehicle, garden, plants_trees, other
    """
    with _conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM assets WHERE category = ? ORDER BY name", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM assets ORDER BY category, name").fetchall()
    return {"count": len(rows), "assets": [_row_to_dict(r) for r in rows]}


def search_assets(query: str) -> dict:
    """Search for assets by name, brand, model, species, or notes.

    query: Search term to match against asset fields
    """
    pattern = f"%{query}%"
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM assets
               WHERE name LIKE ? OR brand LIKE ? OR model LIKE ?
                  OR notes LIKE ? OR plant_species LIKE ?
               ORDER BY name""",
            (pattern, pattern, pattern, pattern, pattern),
        ).fetchall()
    return {"count": len(rows), "assets": [_row_to_dict(r) for r in rows]}


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
    now = datetime.now().isoformat()
    if not completed_date:
        completed_date = date.today().isoformat()
    with _conn() as conn:
        asset = conn.execute("SELECT name FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        cur = conn.execute(
            """INSERT INTO maintenance_tasks
               (asset_id, task_name, completed_date, cost, notes,
                next_due_date, interval_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, task_name, completed_date, cost, notes,
             next_due_date, interval_days, now),
        )
        task_id = cur.lastrowid
    return {
        "status": "logged",
        "task_id": task_id,
        "asset": asset["name"],
        "task": task_name,
        "completed": completed_date,
        "next_due": next_due_date,
    }


def get_upcoming_maintenance(days_ahead: int = 30) -> dict:
    """Get all maintenance tasks due within the next N days, including overdue ones.

    days_ahead: Number of days to look ahead (default 30)
    """
    today = date.today()
    cutoff = (today + timedelta(days=days_ahead)).isoformat()
    today_str = today.isoformat()

    with _conn() as conn:
        rows = conn.execute(
            """SELECT mt.*, a.name as asset_name
               FROM maintenance_tasks mt
               JOIN assets a ON mt.asset_id = a.id
               WHERE mt.next_due_date IS NOT NULL
                 AND mt.next_due_date <= ?
               ORDER BY mt.next_due_date ASC""",
            (cutoff,),
        ).fetchall()

    tasks = []
    for row in rows:
        d = _row_to_dict(row)
        due = date.fromisoformat(d["next_due_date"])
        delta = (due - today).days
        d["days_until_due"] = delta
        d["urgency"] = "overdue" if delta < 0 else "due_soon" if delta <= 7 else "upcoming"
        tasks.append(d)

    return {"count": len(tasks), "as_of": today_str, "days_ahead": days_ahead, "tasks": tasks}


def get_asset_history(asset_id: int) -> dict:
    """Get the full maintenance history and total cost for a specific asset.

    asset_id: ID of the asset
    """
    with _conn() as conn:
        asset = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        rows = conn.execute(
            """SELECT * FROM maintenance_tasks WHERE asset_id = ?
               ORDER BY completed_date DESC, created_at DESC""",
            (asset_id,),
        ).fetchall()
    history = [_row_to_dict(r) for r in rows]
    total_cost = sum(r["cost"] or 0 for r in history)
    return {
        "asset": _row_to_dict(asset),
        "maintenance_count": len(history),
        "total_cost": round(total_cost, 2),
        "history": history,
    }


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
    updates = {
        k: v for k, v in {
            "name": name, "category": category, "brand": brand, "model": model,
            "serial": serial, "purchase_date": purchase_date,
            "purchase_price": purchase_price, "warranty_expiry": warranty_expiry,
            "location": location, "notes": notes, "plant_species": plant_species,
            "plant_size": plant_size, "planting_date": planting_date,
            "plant_notes": plant_notes,
        }.items() if v is not None
    }
    if not updates:
        return {"status": "no_change"}
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [asset_id]
    with _conn() as conn:
        asset = conn.execute("SELECT name FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        conn.execute(f"UPDATE assets SET {set_clause} WHERE id = ?", values)
    return {"status": "updated", "asset_id": asset_id, "fields_updated": list(updates.keys())}


# ---------------------------------------------------------------------------
# New tools delegating to workflows
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
