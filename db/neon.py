"""NeonProvider: standard PostgreSQL via psycopg3.

Works with Neon or any standard PostgreSQL database.
Requires DATABASE_URL in the environment.
"""
from __future__ import annotations

import os
import threading
from datetime import date, datetime, timedelta

import psycopg
from psycopg.rows import dict_row

# Idempotent DDL — every statement is guarded (IF NOT EXISTS / IF EXISTS).
# Safe to run on every startup.
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_memory (
    id          SERIAL PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semantic_memory (
    id          SERIAL PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   TEXT NOT NULL,
    metadata    TEXT,
    created_at  TEXT DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assets (
    id              SERIAL PRIMARY KEY,
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
    id              SERIAL PRIMARY KEY,
    asset_id        INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    task_name       TEXT NOT NULL,
    scheduled_date  TEXT,
    completed_date  TEXT,
    cost            REAL,
    notes           TEXT,
    next_due_date   TEXT,
    interval_days   INTEGER,
    created_at      TEXT NOT NULL
);

ALTER TABLE assets            ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE agent_memory      ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

-- Vehicle-specific typed columns
ALTER TABLE assets ADD COLUMN IF NOT EXISTS rego_plate      TEXT;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS odometer_km     INTEGER;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS next_service_km INTEGER;

-- Plant indoor/outdoor flag
ALTER TABLE assets ADD COLUMN IF NOT EXISTS is_indoor BOOLEAN;

CREATE INDEX IF NOT EXISTS assets_user_id_idx ON assets(user_id);
CREATE INDEX IF NOT EXISTS maintenance_tasks_user_id_idx ON maintenance_tasks(user_id);

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_agent_name_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS agent_memory_user_agent_key ON agent_memory(user_id, agent_name, key);

DELETE FROM maintenance_tasks WHERE user_id IS NULL;
DELETE FROM assets WHERE user_id IS NULL;
"""


class NeonProvider:
    """psycopg3 implementation — one thread-local connection per thread."""

    def __init__(self) -> None:
        self._local = threading.local()

    def _conn(self) -> psycopg.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None or conn.closed:
            url = os.environ.get("DATABASE_URL")
            if not url:
                raise RuntimeError("DATABASE_URL must be set in .env")
            self._local.conn = psycopg.connect(url, row_factory=dict_row, autocommit=True)
        return self._local.conn

    # -- Schema --

    def ensure_schema(self) -> None:
        with self._conn().cursor() as cur:
            cur.execute(_SCHEMA_SQL)
        print("Schema ready.")

    # -- Assets --

    def add_asset(
        self,
        name: str,
        category: str,
        brand: str | None = None,
        model: str | None = None,
        serial: str | None = None,
        purchase_date: str | None = None,
        purchase_price: float | None = None,
        warranty_expiry: str | None = None,
        location: str | None = None,
        notes: str | None = None,
        plant_species: str | None = None,
        plant_size: str | None = None,
        planting_date: str | None = None,
        plant_notes: str | None = None,
        is_indoor: bool | None = None,
        rego_plate: str | None = None,
        odometer_km: int | None = None,
        next_service_km: int | None = None,
        user_id: str | None = None,
    ) -> dict:
        with self._conn().cursor() as cur:
            cur.execute(
                """
                INSERT INTO assets (
                    name, category, brand, model, serial,
                    purchase_date, purchase_price, warranty_expiry,
                    location, notes, plant_species, plant_size,
                    planting_date, plant_notes, is_indoor,
                    rego_plate, odometer_km, next_service_km,
                    user_id, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                [
                    name, category, brand, model, serial,
                    purchase_date, purchase_price, warranty_expiry,
                    location, notes, plant_species, plant_size,
                    planting_date, plant_notes, is_indoor,
                    rego_plate, odometer_km, next_service_km,
                    user_id, datetime.now().isoformat(),
                ],
            )
            asset_id = cur.fetchone()["id"]
        return {"status": "created", "asset_id": asset_id, "name": name}

    def list_assets(self, user_id: str, category: str | None = None) -> dict:
        with self._conn().cursor() as cur:
            if category:
                cur.execute(
                    "SELECT * FROM assets WHERE user_id=%s AND category=%s ORDER BY category, name",
                    [user_id, category],
                )
            else:
                cur.execute(
                    "SELECT * FROM assets WHERE user_id=%s ORDER BY category, name",
                    [user_id],
                )
            rows = [dict(r) for r in cur.fetchall()]
        return {"count": len(rows), "assets": rows}

    def search_assets(self, user_id: str, query: str) -> dict:
        p = f"%{query}%"
        with self._conn().cursor() as cur:
            cur.execute(
                """
                SELECT * FROM assets
                WHERE user_id=%s
                  AND (name ILIKE %s OR brand ILIKE %s OR model ILIKE %s
                       OR notes ILIKE %s OR plant_species ILIKE %s)
                ORDER BY name
                """,
                [user_id, p, p, p, p, p],
            )
            rows = [dict(r) for r in cur.fetchall()]
        return {"count": len(rows), "assets": rows}

    def log_maintenance(
        self,
        user_id: str,
        asset_id: int,
        task_name: str,
        completed_date: str | None = None,
        cost: float | None = None,
        notes: str | None = None,
        next_due_date: str | None = None,
        interval_days: int | None = None,
    ) -> dict:
        with self._conn().cursor() as cur:
            cur.execute(
                "SELECT name FROM assets WHERE id=%s AND user_id=%s",
                [asset_id, user_id],
            )
            asset = cur.fetchone()
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        if not completed_date:
            completed_date = date.today().isoformat()
        with self._conn().cursor() as cur:
            cur.execute(
                """
                INSERT INTO maintenance_tasks
                    (asset_id, task_name, completed_date, cost, notes,
                     next_due_date, interval_days, user_id, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                [
                    asset_id, task_name, completed_date, cost, notes,
                    next_due_date, interval_days, user_id, datetime.now().isoformat(),
                ],
            )
            task_id = cur.fetchone()["id"]
        return {
            "status": "logged",
            "task_id": task_id,
            "asset": asset["name"],
            "task": task_name,
            "completed": completed_date,
            "next_due": next_due_date,
        }

    def get_upcoming_maintenance(self, user_id: str, days_ahead: int = 30) -> dict:
        today = date.today()
        cutoff = (today + timedelta(days=days_ahead)).isoformat()
        with self._conn().cursor() as cur:
            cur.execute(
                """
                SELECT mt.*, a.name AS asset_name, a.category AS category
                FROM maintenance_tasks mt
                JOIN assets a ON a.id = mt.asset_id
                WHERE mt.user_id=%s
                  AND mt.next_due_date IS NOT NULL
                  AND mt.next_due_date <= %s
                ORDER BY mt.next_due_date
                """,
                [user_id, cutoff],
            )
            rows = [dict(r) for r in cur.fetchall()]
        tasks = []
        for row in rows:
            delta = (date.fromisoformat(row["next_due_date"]) - today).days
            row["days_until_due"] = delta
            row["urgency"] = (
                "overdue" if delta < 0 else "due_soon" if delta <= 7 else "upcoming"
            )
            tasks.append(row)
        return {
            "count": len(tasks),
            "as_of": today.isoformat(),
            "days_ahead": days_ahead,
            "tasks": tasks,
        }

    def get_asset_history(self, user_id: str, asset_id: int) -> dict:
        with self._conn().cursor() as cur:
            cur.execute(
                "SELECT * FROM assets WHERE id=%s AND user_id=%s",
                [asset_id, user_id],
            )
            asset = cur.fetchone()
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        with self._conn().cursor() as cur:
            cur.execute(
                """
                SELECT * FROM maintenance_tasks
                WHERE asset_id=%s AND user_id=%s
                ORDER BY completed_date DESC, created_at DESC
                """,
                [asset_id, user_id],
            )
            history = [dict(r) for r in cur.fetchall()]
        total_cost = sum(r["cost"] or 0 for r in history)
        return {
            "asset": dict(asset),
            "maintenance_count": len(history),
            "total_cost": round(total_cost, 2),
            "history": history,
        }

    def get_expiring_warranties(self, user_id: str, days_ahead: int = 90) -> dict:
        today = date.today()
        cutoff = (today + timedelta(days=days_ahead)).isoformat()
        today_str = today.isoformat()
        with self._conn().cursor() as cur:
            cur.execute(
                """
                SELECT id, name, category, brand, model, warranty_expiry
                FROM assets
                WHERE user_id=%s
                  AND warranty_expiry IS NOT NULL
                  AND warranty_expiry >= %s
                  AND warranty_expiry <= %s
                ORDER BY warranty_expiry
                """,
                [user_id, today_str, cutoff],
            )
            rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            delta = (date.fromisoformat(row["warranty_expiry"]) - today).days
            row["days_until_expiry"] = delta
            row["urgency"] = "due_soon" if delta <= 30 else "upcoming"
        return {"count": len(rows), "days_ahead": days_ahead, "warranties": rows}

    def update_asset(self, user_id: str, asset_id: int, updates: dict) -> dict:
        if not updates:
            return {"status": "no_change"}
        with self._conn().cursor() as cur:
            cur.execute(
                "SELECT id FROM assets WHERE id=%s AND user_id=%s",
                [asset_id, user_id],
            )
            if not cur.fetchone():
                return {"status": "error", "message": f"No asset found with id {asset_id}"}
            set_clause = ", ".join(f"{col}=%s" for col in updates)
            cur.execute(
                f"UPDATE assets SET {set_clause} WHERE id=%s AND user_id=%s",
                [*updates.values(), asset_id, user_id],
            )
        return {"status": "updated", "asset_id": asset_id, "fields_updated": list(updates.keys())}

    # -- Auth / Users --

    def authenticate(self, email: str, password: str) -> dict | None:
        import bcrypt
        with self._conn().cursor() as cur:
            cur.execute(
                "SELECT id, email, role, is_active, created_at, password_hash FROM users WHERE email=%s",
                [email],
            )
            user = cur.fetchone()
        if not user or not user["is_active"]:
            return None
        try:
            if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                return None
        except (ValueError, TypeError):
            return None
        result = dict(user)
        result.pop("password_hash")
        return result

    def list_users(self) -> list[dict]:
        with self._conn().cursor() as cur:
            cur.execute(
                "SELECT id, email, role, is_active, created_at FROM users ORDER BY created_at"
            )
            return [dict(r) for r in cur.fetchall()]

    def get_user(self, user_id: str) -> dict | None:
        with self._conn().cursor() as cur:
            cur.execute(
                "SELECT id, email, role, is_active, created_at FROM users WHERE id=%s",
                [user_id],
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def email_exists(self, email: str) -> bool:
        with self._conn().cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s", [email])
            return cur.fetchone() is not None

    def create_user(self, email: str, password: str, role: str = "user") -> dict:
        import bcrypt
        ph = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        with self._conn().cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (%s, %s, %s)
                RETURNING id, email, role, is_active, created_at
                """,
                [email, ph, role],
            )
            return dict(cur.fetchone())

    def set_active(self, user_id: str, is_active: bool) -> None:
        with self._conn().cursor() as cur:
            cur.execute("UPDATE users SET is_active=%s WHERE id=%s", [is_active, user_id])

    def set_role(self, user_id: str, role: str) -> None:
        with self._conn().cursor() as cur:
            cur.execute("UPDATE users SET role=%s WHERE id=%s", [role, user_id])

    def reset_password(self, user_id: str, new_password: str) -> None:
        import bcrypt
        ph = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        with self._conn().cursor() as cur:
            cur.execute("UPDATE users SET password_hash=%s WHERE id=%s", [ph, user_id])

    def delete_user(self, user_id: str) -> None:
        with self._conn().cursor() as cur:
            cur.execute("DELETE FROM users WHERE id=%s", [user_id])

    def is_last_active_admin(self, user_id: str) -> bool:
        with self._conn().cursor() as cur:
            cur.execute("SELECT id FROM users WHERE role='admin' AND is_active=true")
            admin_ids = {str(r["id"]) for r in cur.fetchall()}
        return admin_ids == {str(user_id)}

    def bootstrap_admin(self) -> None:
        with self._conn().cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM users")
            count = cur.fetchone()["count"]
        if count > 0:
            return
        email = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")
        if not email or not password:
            print(
                "No users found and ADMIN_EMAIL/ADMIN_PASSWORD not set — "
                "set them in .env to bootstrap the first admin account."
            )
            return
        self.create_user(email.strip().lower(), password, role="admin")
        print(f"Bootstrapped admin account: {email.strip().lower()}")

    # -- Long-term (key-value) memory --

    def memory_set(
        self, user_id: str, agent_name: str, key: str, value: str, updated_at: str
    ) -> None:
        with self._conn().cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_memory (user_id, agent_name, key, value, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, agent_name, key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
                """,
                [user_id, agent_name, key, value, updated_at],
            )

    def memory_get(self, user_id: str, agent_name: str, key: str) -> str | None:
        with self._conn().cursor() as cur:
            cur.execute(
                "SELECT value FROM agent_memory WHERE user_id=%s AND agent_name=%s AND key=%s",
                [user_id, agent_name, key],
            )
            row = cur.fetchone()
        return row["value"] if row else None

    def memory_delete(self, user_id: str, agent_name: str, key: str) -> None:
        with self._conn().cursor() as cur:
            cur.execute(
                "DELETE FROM agent_memory WHERE user_id=%s AND agent_name=%s AND key=%s",
                [user_id, agent_name, key],
            )

    def memory_get_all(self, user_id: str, agent_name: str) -> list[dict]:
        with self._conn().cursor() as cur:
            cur.execute(
                "SELECT key, value FROM agent_memory WHERE user_id=%s AND agent_name=%s",
                [user_id, agent_name],
            )
            return [dict(r) for r in cur.fetchall()]

    # -- Semantic memory --

    def semantic_store(
        self, agent_name: str, content: str, embedding: str, metadata: str
    ) -> int:
        with self._conn().cursor() as cur:
            cur.execute(
                """
                INSERT INTO semantic_memory (agent_name, content, embedding, metadata)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                [agent_name, content, embedding, metadata],
            )
            return cur.fetchone()["id"]

    def semantic_retrieve(self, agent_name: str) -> list[dict]:
        with self._conn().cursor() as cur:
            cur.execute(
                "SELECT id, content, embedding, metadata FROM semantic_memory WHERE agent_name=%s",
                [agent_name],
            )
            return [dict(r) for r in cur.fetchall()]

    def semantic_clear(self, agent_name: str) -> None:
        with self._conn().cursor() as cur:
            cur.execute("DELETE FROM semantic_memory WHERE agent_name=%s", [agent_name])

    def list_maintenance_tasks(self, user_id: str, since_date: str | None = None) -> list[dict]:
        with self._conn().cursor() as cur:
            if since_date:
                cur.execute(
                    "SELECT * FROM maintenance_tasks WHERE user_id=%s AND completed_date >= %s",
                    [user_id, since_date],
                )
            else:
                cur.execute(
                    "SELECT * FROM maintenance_tasks WHERE user_id=%s",
                    [user_id],
                )
            return [dict(r) for r in cur.fetchall()]
