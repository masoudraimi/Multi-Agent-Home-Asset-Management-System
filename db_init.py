"""Create the SQLite database schema and populate with realistic seed data."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "home_assets.db"


DDL = """
CREATE TABLE IF NOT EXISTS assets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL,
    brand           TEXT,
    model           TEXT,
    serial          TEXT,
    purchase_date   TEXT,
    purchase_price  REAL,
    warranty_expiry TEXT,
    location        TEXT,
    notes           TEXT,
    plant_species   TEXT,
    plant_size      TEXT,
    planting_date   TEXT,
    plant_notes     TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id        INTEGER NOT NULL REFERENCES assets(id),
    task_name       TEXT NOT NULL,
    scheduled_date  TEXT,
    completed_date  TEXT,
    cost            REAL,
    notes           TEXT,
    next_due_date   TEXT,
    interval_days   INTEGER,
    created_at      TEXT NOT NULL
);
"""

SEED_ASSETS = [
    # (name, category, brand, model, serial, purchase_date, price, warranty_expiry, location, notes, plant_species, plant_size, planting_date, plant_notes)
    ("Dishwasher", "appliances", "Bosch", "SMS6ZCI00A", "BOS-2021-88341", "2021-03-15", 1299.0, "2027-03-15", "Kitchen", "Stainless steel interior", None, None, None, None),
    ("Refrigerator", "appliances", "Samsung", "SRF801GDLS", "SAM-2020-55219", "2020-08-10", 2499.0, "2025-08-10", "Kitchen", "French door, ice maker", None, None, None, None),
    ("Washing Machine", "appliances", "LG", "WTR1232C", "LG-2022-33901", "2022-01-20", 999.0, "2027-01-20", "Laundry", "Front loader 8kg", None, None, None, None),
    ("HVAC System", "HVAC", "Daikin", "FTXM50W", "DAI-2019-70042", "2019-06-01", 3800.0, "2024-06-01", "Whole house", "Split system, 5kW. Warranty expired.", None, None, None, None),
    ("Hot Water System", "plumbing", "Rheem", "522365", "RHM-2020-19283", "2020-02-14", 1450.0, "2025-02-14", "Outside utility", "Gas continuous flow", None, None, None, None),
    ("Smoke Alarm - Kitchen", "electrical", "Clipsal", "755PSMA", None, "2021-09-01", 85.0, None, "Kitchen", "Photoelectric + CO", None, None, None, None),
    ("Smoke Alarm - Hallway", "electrical", "Clipsal", "755PSMA", None, "2021-09-01", 85.0, None, "Hallway", "Photoelectric", None, None, None, None),
    ("Garage Door Opener", "exterior", "Merlin", "MR865EVO", "MRL-2020-44821", "2020-05-10", 650.0, "2023-05-10", "Garage", "Belt drive, warranty expired", None, None, None, None),
    ("Lawn Mower", "garden", "Honda", "HRU196M2", "HON-2021-29031", "2021-11-01", 879.0, "2024-11-01", "Shed", "Self-propelled", None, None, None, None),
    ("Car - Toyota Camry", "vehicle", "Toyota", "Camry 2019 Hybrid", "2T1BURHE0JC037610", "2019-04-15", 38000.0, "2024-04-15", "Garage", "Petrol-electric hybrid, rego due April", None, None, None, None),
    # Plants and trees
    ("Lemon Tree", "plants_trees", None, None, None, None, None, None, "Back yard, east corner", "Meyer lemon, in ground", "lemon tree", "large", "2020-09-01", "Full sun, good drainage. Fruiting well."),
    ("Front Garden Agapanthus", "plants_trees", None, None, None, None, None, None, "Front garden bed", "4 large clumps along the fence", "agapanthus", "mature", "2018-03-01", "Very established, needs dividing"),
    ("Rose Bush - Red", "plants_trees", None, None, None, None, None, None, "Back yard, near deck", "Climbing rose on trellis", "rose", "large", "2021-11-15", "Needs regular deadheading and rust prevention"),
]

SEED_MAINTENANCE = [
    # (asset_id, task_name, completed_date, cost, notes, next_due_date, interval_days)
    # Dishwasher (id=1)
    (1, "Descale and clean filter", "2024-06-15", 0.0, "Used Finish descaler", "2025-06-15", 365),
    (1, "Check door seals", "2024-06-15", 0.0, "Seals look fine", None, None),
    # Refrigerator (id=2)
    (2, "Clean condenser coils", "2024-11-20", 0.0, "Vacuumed dust buildup", "2025-11-20", 365),
    (2, "Replace water filter", "2025-02-01", 45.0, "Genuine Samsung filter", "2025-08-01", 180),
    # Washing Machine (id=3)
    (3, "Clean drum and seals", "2025-04-10", 0.0, "Used machine cleaner tablet", "2025-07-10", 90),
    (3, "Check hoses", "2025-04-10", 0.0, "No leaks detected", "2026-04-10", 365),
    # HVAC (id=4)
    (4, "Replace filters", "2025-03-01", 35.0, "3M electrostatic filters x2", "2025-06-01", 90),
    (4, "Annual service", "2024-09-15", 220.0, "Gas top-up, coil clean, full check", "2025-09-15", 365),
    # Hot Water (id=5)
    (5, "Annual gas service", "2024-12-10", 185.0, "Replaced sacrificial anode", "2025-12-10", 365),
    # Smoke Alarms (id=6, 7)
    (6, "Test alarm", "2025-05-01", 0.0, "Working", "2025-11-01", 180),
    (7, "Test alarm", "2025-05-01", 0.0, "Working", "2025-11-01", 180),
    (6, "Replace battery", "2024-10-01", 8.0, "9V Duracell", "2025-10-01", 365),
    (7, "Replace battery", "2024-10-01", 8.0, "9V Duracell", "2025-10-01", 365),
    # Garage Door (id=8)
    (8, "Lubricate tracks and rollers", "2025-01-15", 12.0, "Used white lithium grease", "2025-07-15", 180),
    # Lawn Mower (id=9)
    (9, "Sharpen blade + oil change", "2025-09-20", 55.0, "Pre-season service", "2026-09-20", 365),
    (9, "Air filter replacement", "2025-09-20", 18.0, "Honda OEM filter", "2026-09-20", 365),
    # Car (id=10)
    (10, "Scheduled service (30,000km)", "2025-04-20", 380.0, "Oil, filters, brake inspection", "2025-10-20", 180),
    (10, "Tyre rotation", "2025-04-20", 60.0, "Rotated all 4, aligned", "2025-10-20", 180),
    (10, "Registration renewal", "2025-04-15", 820.0, "VicRoads rego", "2026-04-15", 365),
]


def init_db(path: Path = DB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)

    conn.executescript(DDL)

    # Migrate existing DBs: add plant columns if missing
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(assets)").fetchall()}
    for col, coltype in [
        ("plant_species", "TEXT"), ("plant_size", "TEXT"),
        ("planting_date", "TEXT"), ("plant_notes", "TEXT"),
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE assets ADD COLUMN {col} {coltype}")
            print(f"  Migrated: added column '{col}' to assets")

    now = "2025-01-01T00:00:00"
    existing = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    if existing == 0:
        conn.executemany(
            """INSERT INTO assets
               (name, category, brand, model, serial, purchase_date, purchase_price,
                warranty_expiry, location, notes, plant_species, plant_size,
                planting_date, plant_notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(*a, now) for a in SEED_ASSETS],
        )
        conn.executemany(
            """INSERT INTO maintenance_tasks
               (asset_id, task_name, completed_date, cost, notes,
                next_due_date, interval_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(*m, now) for m in SEED_MAINTENANCE],
        )
        print(f"Seeded {len(SEED_ASSETS)} assets and {len(SEED_MAINTENANCE)} maintenance records.")
    else:
        print(f"Database already contains {existing} assets — skipping seed.")

    conn.commit()
    conn.close()
    print(f"Database ready at {path}")


if __name__ == "__main__":
    init_db()
