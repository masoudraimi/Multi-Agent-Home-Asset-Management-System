"""SupabaseProvider: database backend using the Supabase Python SDK.

Requires SUPABASE_URL and SUPABASE_KEY in the environment.
For schema creation also requires SUPABASE_DB_URL or SUPABASE_DB_PASSWORD.
"""
from __future__ import annotations

import os
import re
import time
from datetime import date, datetime, timedelta

import bcrypt
from supabase import Client, create_client

# Shared DDL + Supabase-specific PostgREST cache refresh at the end.
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

CREATE INDEX IF NOT EXISTS assets_user_id_idx ON assets(user_id);
CREATE INDEX IF NOT EXISTS maintenance_tasks_user_id_idx ON maintenance_tasks(user_id);

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_agent_name_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS agent_memory_user_agent_key ON agent_memory(user_id, agent_name, key);

DELETE FROM maintenance_tasks WHERE user_id IS NULL;
DELETE FROM assets WHERE user_id IS NULL;

NOTIFY pgrst, 'reload schema';
"""


class SupabaseProvider:
    """Database backend using the Supabase PostgREST Python SDK."""

    def __init__(self) -> None:
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if not url or not key:
                raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
            self._client = create_client(url, key)
        return self._client

    # -- Schema --

    def _schema_ok(self) -> bool:
        try:
            self._get_client().table("users").select("id").limit(1).execute()
            return True
        except Exception:
            return False

    def _resolve_db_url(self) -> str | None:
        url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
        if url:
            return url
        password = os.environ.get("SUPABASE_DB_PASSWORD")
        supabase_url = os.environ.get("SUPABASE_URL", "")
        m = re.search(r"https://([a-z0-9]+)\.supabase\.co", supabase_url)
        if password and m:
            ref = m.group(1)
            return f"postgresql://postgres:{password}@db.{ref}.supabase.co:5432/postgres"
        return None

    def ensure_schema(self) -> None:
        if self._schema_ok():
            return
        db_url = self._resolve_db_url()
        if not db_url:
            raise RuntimeError(
                "The 'users' table is missing and no database connection string is "
                "available to create it automatically.\n\n"
                "Fix (pick one), then restart:\n"
                "  1. Set SUPABASE_DB_URL=postgresql://... in .env\n"
                "  2. Set SUPABASE_DB_PASSWORD=<db-password> in .env\n"
                "  3. Paste the SQL below into the Supabase SQL editor once.\n\n"
                + _SCHEMA_SQL
            )
        import psycopg
        print("Schema missing — applying multi-user migration...")
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA_SQL)
        for _ in range(20):
            if self._schema_ok():
                print("Schema ready.")
                return
            time.sleep(0.5)
        raise RuntimeError(
            "Schema was created but the Supabase REST API has not picked it up yet. "
            "Wait a few seconds and restart the app, or run "
            "NOTIFY pgrst, 'reload schema'; in the Supabase SQL editor."
        )

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
        user_id: str | None = None,
    ) -> dict:
        row = {
            "name": name, "category": category, "brand": brand, "model": model,
            "serial": serial, "purchase_date": purchase_date,
            "purchase_price": purchase_price, "warranty_expiry": warranty_expiry,
            "location": location, "notes": notes, "plant_species": plant_species,
            "plant_size": plant_size, "planting_date": planting_date,
            "plant_notes": plant_notes, "user_id": user_id,
            "created_at": datetime.now().isoformat(),
        }
        result = self._get_client().table("assets").insert(row).execute()
        asset_id = result.data[0]["id"]
        return {"status": "created", "asset_id": asset_id, "name": name}

    def list_assets(self, user_id: str, category: str | None = None) -> dict:
        q = self._get_client().table("assets").select("*").eq("user_id", user_id)
        if category:
            q = q.eq("category", category)
        rows = q.order("category").order("name").execute().data
        return {"count": len(rows), "assets": rows}

    def search_assets(self, user_id: str, query: str) -> dict:
        p = f"%{query}%"
        rows = (
            self._get_client().table("assets").select("*")
            .eq("user_id", user_id)
            .or_(f"name.ilike.{p},brand.ilike.{p},model.ilike.{p},notes.ilike.{p},plant_species.ilike.{p}")
            .order("name")
            .execute()
            .data
        )
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
        client = self._get_client()
        asset = (
            client.table("assets").select("name")
            .eq("id", asset_id).eq("user_id", user_id).execute().data
        )
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        if not completed_date:
            completed_date = date.today().isoformat()
        row = {
            "asset_id": asset_id, "task_name": task_name,
            "completed_date": completed_date, "cost": cost, "notes": notes,
            "next_due_date": next_due_date, "interval_days": interval_days,
            "user_id": user_id, "created_at": datetime.now().isoformat(),
        }
        result = client.table("maintenance_tasks").insert(row).execute()
        task_id = result.data[0]["id"]
        return {
            "status": "logged", "task_id": task_id,
            "asset": asset[0]["name"], "task": task_name,
            "completed": completed_date, "next_due": next_due_date,
        }

    def get_upcoming_maintenance(self, user_id: str, days_ahead: int = 30) -> dict:
        today = date.today()
        cutoff = (today + timedelta(days=days_ahead)).isoformat()
        rows = (
            self._get_client().table("maintenance_tasks")
            .select("*, assets!inner(name, category)")
            .eq("user_id", user_id)
            .not_.is_("next_due_date", "null")
            .lte("next_due_date", cutoff)
            .order("next_due_date")
            .execute()
            .data
        )
        tasks = []
        for row in rows:
            d = {k: v for k, v in row.items() if k != "assets"}
            d["asset_name"] = row["assets"]["name"]
            d["category"] = row["assets"]["category"]
            delta = (date.fromisoformat(d["next_due_date"]) - today).days
            d["days_until_due"] = delta
            d["urgency"] = "overdue" if delta < 0 else "due_soon" if delta <= 7 else "upcoming"
            tasks.append(d)
        return {
            "count": len(tasks),
            "as_of": today.isoformat(),
            "days_ahead": days_ahead,
            "tasks": tasks,
        }

    def get_asset_history(self, user_id: str, asset_id: int) -> dict:
        client = self._get_client()
        asset = (
            client.table("assets").select("*")
            .eq("id", asset_id).eq("user_id", user_id).execute().data
        )
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        history = (
            client.table("maintenance_tasks").select("*")
            .eq("asset_id", asset_id).eq("user_id", user_id)
            .order("completed_date", desc=True).order("created_at", desc=True)
            .execute().data
        )
        total_cost = sum(r["cost"] or 0 for r in history)
        return {
            "asset": asset[0],
            "maintenance_count": len(history),
            "total_cost": round(total_cost, 2),
            "history": history,
        }

    def update_asset(self, user_id: str, asset_id: int, updates: dict) -> dict:
        if not updates:
            return {"status": "no_change"}
        client = self._get_client()
        asset = (
            client.table("assets").select("name")
            .eq("id", asset_id).eq("user_id", user_id).execute().data
        )
        if not asset:
            return {"status": "error", "message": f"No asset found with id {asset_id}"}
        client.table("assets").update(updates).eq("id", asset_id).eq("user_id", user_id).execute()
        return {"status": "updated", "asset_id": asset_id, "fields_updated": list(updates.keys())}

    # -- Auth / Users --

    def authenticate(self, email: str, password: str) -> dict | None:
        rows = (
            self._get_client().table("users")
            .select("id, email, role, is_active, created_at, password_hash")
            .eq("email", email).execute().data
        )
        if not rows:
            return None
        user = rows[0]
        if not user.get("is_active"):
            return None
        try:
            if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                return None
        except (ValueError, TypeError):
            return None
        user.pop("password_hash", None)
        return user

    def list_users(self) -> list[dict]:
        return (
            self._get_client().table("users")
            .select("id, email, role, is_active, created_at")
            .order("created_at").execute().data
        )

    def get_user(self, user_id: str) -> dict | None:
        rows = (
            self._get_client().table("users")
            .select("id, email, role, is_active, created_at")
            .eq("id", user_id).execute().data
        )
        return rows[0] if rows else None

    def email_exists(self, email: str) -> bool:
        rows = self._get_client().table("users").select("id").eq("email", email).execute().data
        return bool(rows)

    def create_user(self, email: str, password: str, role: str = "user") -> dict:
        ph = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        inserted = self._get_client().table("users").insert(
            {"email": email, "password_hash": ph, "role": role}
        ).execute().data[0]
        return {k: inserted[k] for k in ("id", "email", "role", "is_active", "created_at")}

    def set_active(self, user_id: str, is_active: bool) -> None:
        self._get_client().table("users").update({"is_active": is_active}).eq("id", user_id).execute()

    def set_role(self, user_id: str, role: str) -> None:
        self._get_client().table("users").update({"role": role}).eq("id", user_id).execute()

    def reset_password(self, user_id: str, new_password: str) -> None:
        ph = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        self._get_client().table("users").update({"password_hash": ph}).eq("id", user_id).execute()

    def delete_user(self, user_id: str) -> None:
        self._get_client().table("users").delete().eq("id", user_id).execute()

    def is_last_active_admin(self, user_id: str) -> bool:
        admins = (
            self._get_client().table("users").select("id")
            .eq("role", "admin").eq("is_active", True).execute().data
        )
        admin_ids = {a["id"] for a in admins}
        return admin_ids == {user_id}

    def bootstrap_admin(self) -> None:
        count = self._get_client().table("users").select("id", count="exact").execute().count or 0
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
        self._get_client().table("agent_memory").upsert(
            {
                "user_id": user_id,
                "agent_name": agent_name,
                "key": key,
                "value": value,
                "updated_at": updated_at,
            },
            on_conflict="user_id,agent_name,key",
        ).execute()

    def memory_get(self, user_id: str, agent_name: str, key: str) -> str | None:
        rows = (
            self._get_client().table("agent_memory").select("value")
            .eq("user_id", user_id).eq("agent_name", agent_name).eq("key", key)
            .execute().data
        )
        return rows[0]["value"] if rows else None

    def memory_delete(self, user_id: str, agent_name: str, key: str) -> None:
        (
            self._get_client().table("agent_memory").delete()
            .eq("user_id", user_id).eq("agent_name", agent_name).eq("key", key)
            .execute()
        )

    def memory_get_all(self, user_id: str, agent_name: str) -> list[dict]:
        rows = (
            self._get_client().table("agent_memory").select("key, value")
            .eq("user_id", user_id).eq("agent_name", agent_name)
            .execute().data
        )
        return rows

    # -- Semantic memory --

    def semantic_store(
        self, agent_name: str, content: str, embedding: str, metadata: str
    ) -> int:
        result = self._get_client().table("semantic_memory").insert({
            "agent_name": agent_name,
            "content": content,
            "embedding": embedding,
            "metadata": metadata,
        }).execute()
        return result.data[0]["id"]

    def semantic_retrieve(self, agent_name: str) -> list[dict]:
        return (
            self._get_client().table("semantic_memory")
            .select("id, content, embedding, metadata")
            .eq("agent_name", agent_name)
            .execute().data
        )

    def semantic_clear(self, agent_name: str) -> None:
        self._get_client().table("semantic_memory").delete().eq("agent_name", agent_name).execute()

    def list_maintenance_tasks(self, user_id: str, since_date: str | None = None) -> list[dict]:
        q = self._get_client().table("maintenance_tasks").select("*").eq("user_id", user_id)
        if since_date:
            q = q.gte("completed_date", since_date)
        return q.execute().data
