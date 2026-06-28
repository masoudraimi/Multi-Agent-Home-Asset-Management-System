"""First-run database bootstrap.

Schema (tables) must already exist — create them once via the Supabase SQL Editor
(see README). This module is multi-user: it no longer seeds sample assets. Each
user starts with an empty inventory. On first run it bootstraps an admin account
from the ADMIN_EMAIL / ADMIN_PASSWORD env vars.
"""

from core.auth import bootstrap_admin


def init_db() -> None:
    bootstrap_admin()
    print("Database ready.")


if __name__ == "__main__":
    init_db()
