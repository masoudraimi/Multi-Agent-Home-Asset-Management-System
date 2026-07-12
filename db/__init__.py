"""Database provider factory.

Set DB_PROVIDER in .env to select the backend:
  DB_PROVIDER=neon      (default) — psycopg3, requires DATABASE_URL
  DB_PROVIDER=supabase  — Supabase SDK, requires SUPABASE_URL + SUPABASE_KEY
"""
from __future__ import annotations

import os

from db.base import DBProvider

_provider: DBProvider | None = None


def get_provider() -> DBProvider:
    global _provider
    if _provider is None:
        name = os.environ.get("DB_PROVIDER", "neon").lower()
        if name == "supabase":
            from db.supabase import SupabaseProvider
            _provider = SupabaseProvider()
        else:
            from db.neon import NeonProvider
            _provider = NeonProvider()
    return _provider
