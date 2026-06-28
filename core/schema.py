"""Schema bootstrap: ensure the multi-user tables/columns exist on startup.

The Supabase REST client (PostgREST) cannot run DDL, so schema creation goes
over a direct Postgres connection. The connection string is resolved from:

  1. SUPABASE_DB_URL  — full postgres connection string (preferred), or
  2. SUPABASE_DB_PASSWORD — combined with the project ref from SUPABASE_URL to
     build  postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres

If neither is set and the schema is missing, we raise with the exact SQL so it
can be pasted into the Supabase SQL editor manually.
"""

from __future__ import annotations

import os
import re
import time

from db_conn import get_client

# Idempotent migration. Safe to run on every startup: every statement is
# guarded (IF NOT EXISTS / IF EXISTS) and the NULL-owner cleanup only removes
# legacy single-tenant rows that were never assigned to a user.
SCHEMA_SQL = """
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

-- Add multi-user ownership columns (idempotent).
ALTER TABLE assets            ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE agent_memory      ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS assets_user_id_idx ON assets(user_id);
CREATE INDEX IF NOT EXISTS maintenance_tasks_user_id_idx ON maintenance_tasks(user_id);

-- agent_memory uniqueness must include user_id (was agent_name,key).
ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_agent_name_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS agent_memory_user_agent_key ON agent_memory(user_id, agent_name, key);

-- Remove legacy single-tenant rows that have no owner (wipe-and-fresh).
DELETE FROM maintenance_tasks WHERE user_id IS NULL;
DELETE FROM assets WHERE user_id IS NULL;

-- Tell PostgREST (the REST API) to reload its schema cache so the new tables
-- are immediately visible to the Supabase client.
NOTIFY pgrst, 'reload schema';
"""


def _schema_ok() -> bool:
    """Cheap check via the REST client: does the users table exist and respond?"""
    try:
        get_client().table("users").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def _resolve_db_url() -> str | None:
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


def ensure_schema() -> None:
    """Create the multi-user schema if missing. No-op when already present."""
    if _schema_ok():
        return

    db_url = _resolve_db_url()
    if not db_url:
        raise RuntimeError(
            "The 'users' table is missing and no database connection string is "
            "available to create it automatically.\n\n"
            "Fix (pick one), then restart:\n"
            "  1. In Supabase: Connect -> Connection string -> URI, copy it, and set\n"
            "     SUPABASE_DB_URL=postgresql://... in .env  (URI already includes the password)\n"
            "  2. Or set SUPABASE_DB_PASSWORD=<db-password> in .env\n"
            "  3. Or paste the SQL below into the Supabase SQL editor once.\n\n"
            + SCHEMA_SQL
        )

    import psycopg

    print("Schema missing — applying multi-user migration...")
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)

    # PostgREST reloads its schema cache asynchronously after the NOTIFY above.
    # Poll the REST endpoint until the new 'users' table becomes visible so the
    # very next Supabase-client call (bootstrap_admin) doesn't hit a stale cache.
    for _ in range(20):
        if _schema_ok():
            print("Schema ready.")
            return
        time.sleep(0.5)

    raise RuntimeError(
        "Schema was created, but the Supabase REST API has not picked it up yet. "
        "Wait a few seconds and restart the app, or run "
        "NOTIFY pgrst, 'reload schema'; in the Supabase SQL editor."
    )
