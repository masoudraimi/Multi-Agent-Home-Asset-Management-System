import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).parent.parent / "data" / "home_assets.db"

TOOL_SCHEMAS = []


def tool(func):
    """Register a function as an agent tool and generate its OpenAI-compatible schema."""
    import inspect

    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""
    # Parse "param: description" lines from docstring
    param_docs: dict[str, str] = {}
    for line in doc.splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("Returns"):
            parts = line.split(":", 1)
            if parts[0].strip() in sig.parameters:
                param_docs[parts[0].strip()] = parts[1].strip()

    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        prop: dict[str, Any] = {"description": param_docs.get(name, name)}
        annotation = param.annotation
        origin = getattr(annotation, "__origin__", None)
        if origin is type(None):
            prop["type"] = "null"
        elif annotation == int:
            prop["type"] = "integer"
        elif annotation == float:
            prop["type"] = "number"
        elif annotation == bool:
            prop["type"] = "boolean"
        else:
            prop["type"] = "string"

        # Optional[X] — check for Union with None
        if origin is not None:
            args = getattr(annotation, "__args__", ())
            if type(None) in args:
                inner = [a for a in args if a is not type(None)]
                if inner:
                    t = inner[0]
                    if t == int:
                        prop["type"] = "integer"
                    elif t == float:
                        prop["type"] = "number"
                    else:
                        prop["type"] = "string"
            else:
                prop["type"] = "string"

        if param.default is inspect.Parameter.empty:
            required.append(name)
        properties[name] = prop

    schema = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc.splitlines()[0] if doc else func.__name__,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
    TOOL_SCHEMAS.append(schema)
    return func


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


@tool
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
) -> dict:
    """Register a new home asset in the database.

    name: Human-readable name, e.g. 'Bosch Dishwasher'
    category: One of: appliances, HVAC, plumbing, electrical, exterior, vehicle, garden, other
    brand: Manufacturer brand name
    model: Model number or name
    serial: Serial number
    purchase_date: ISO date string YYYY-MM-DD
    purchase_price: Purchase price in dollars
    warranty_expiry: ISO date string YYYY-MM-DD when warranty expires
    location: Room or area, e.g. 'Kitchen', 'Garage'
    notes: Any additional notes
    """
    now = datetime.now().isoformat()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO assets
               (name, category, brand, model, serial, purchase_date, purchase_price,
                warranty_expiry, location, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, category, brand, model, serial, purchase_date, purchase_price,
             warranty_expiry, location, notes, now),
        )
        asset_id = cur.lastrowid
    return {"status": "created", "asset_id": asset_id, "name": name}


@tool
def list_assets(category: Optional[str] = None) -> dict:
    """List all home assets, optionally filtered by category.

    category: Optional filter — one of: appliances, HVAC, plumbing, electrical, exterior, vehicle, garden, other
    """
    with _conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM assets WHERE category = ? ORDER BY name", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM assets ORDER BY category, name").fetchall()
    assets = [_row_to_dict(r) for r in rows]
    return {"count": len(assets), "assets": assets}


@tool
def search_assets(query: str) -> dict:
    """Search for assets by name, brand, model, or notes using full-text search.

    query: Search term to match against asset name, brand, model, and notes
    """
    pattern = f"%{query}%"
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM assets
               WHERE name LIKE ? OR brand LIKE ? OR model LIKE ? OR notes LIKE ?
               ORDER BY name""",
            (pattern, pattern, pattern, pattern),
        ).fetchall()
    assets = [_row_to_dict(r) for r in rows]
    return {"count": len(assets), "assets": assets}


@tool
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

    asset_id: ID of the asset (from list_assets or search_assets)
    task_name: Description of the task, e.g. 'Filter replacement', 'Annual service'
    completed_date: ISO date YYYY-MM-DD when the task was done (leave null if scheduled only)
    cost: Cost of the maintenance in dollars
    notes: Additional notes about the work done
    next_due_date: ISO date YYYY-MM-DD when this task is next due
    interval_days: Recurring interval in days, e.g. 90 for quarterly
    """
    now = datetime.now().isoformat()
    if not completed_date:
        completed_date = date.today().isoformat()
    with _conn() as conn:
        # Verify asset exists
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


@tool
def get_upcoming_maintenance(days_ahead: int = 30) -> dict:
    """Get all maintenance tasks due within the next N days, including overdue ones.

    days_ahead: Number of days to look ahead (default 30). Always includes overdue tasks.
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
        if delta < 0:
            urgency = "overdue"
        elif delta <= 7:
            urgency = "due_soon"
        else:
            urgency = "upcoming"
        d["days_until_due"] = delta
        d["urgency"] = urgency
        tasks.append(d)

    return {"count": len(tasks), "as_of": today_str, "days_ahead": days_ahead, "tasks": tasks}


@tool
def get_asset_history(asset_id: int) -> dict:
    """Get the full maintenance history for a specific asset.

    asset_id: ID of the asset (from list_assets or search_assets)
    """
    with _conn() as conn:
        asset = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        rows = conn.execute(
            """SELECT * FROM maintenance_tasks
               WHERE asset_id = ?
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


@tool
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
) -> dict:
    """Update one or more fields on an existing asset.

    asset_id: ID of the asset to update
    name: New name for the asset
    category: New category
    brand: New brand
    model: New model number
    serial: New serial number
    purchase_date: New purchase date YYYY-MM-DD
    purchase_price: New purchase price
    warranty_expiry: New warranty expiry date YYYY-MM-DD
    location: New location
    notes: New notes (replaces existing)
    """
    updates = {
        k: v for k, v in {
            "name": name, "category": category, "brand": brand, "model": model,
            "serial": serial, "purchase_date": purchase_date,
            "purchase_price": purchase_price, "warranty_expiry": warranty_expiry,
            "location": location, "notes": notes,
        }.items() if v is not None
    }
    if not updates:
        return {"status": "no_change", "message": "No fields provided to update"}

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [asset_id]
    with _conn() as conn:
        asset = conn.execute("SELECT name FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        conn.execute(f"UPDATE assets SET {set_clause} WHERE id = ?", values)
    return {"status": "updated", "asset_id": asset_id, "fields_updated": list(updates.keys())}


TOOL_DISPATCH = {
    "add_asset": add_asset,
    "list_assets": list_assets,
    "search_assets": search_assets,
    "log_maintenance": log_maintenance,
    "get_upcoming_maintenance": get_upcoming_maintenance,
    "get_asset_history": get_asset_history,
    "update_asset": update_asset,
}
