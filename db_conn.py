"""Supabase client factory — single source of truth for all database access.

Usage:
    from db_conn import get_client

    client = get_client()
    data = client.table("assets").select("*").execute().data
"""
import os

from supabase import Client, create_client

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        _client = create_client(url, key)
    return _client
