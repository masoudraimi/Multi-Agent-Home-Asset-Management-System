"""Long-term memory: key-value store per agent, backed by SQLite agent_memory table."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "home_assets.db"


class LongTermMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def set(self, key: str, value: object) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT INTO agent_memory (agent_name, key, value, updated_at)
                   VALUES (?, ?, ?, datetime('now'))
                   ON CONFLICT(agent_name, key)
                   DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (self.agent_name, key, json.dumps(value)),
            )

    def get(self, key: str, default: object = None) -> object:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT value FROM agent_memory WHERE agent_name=? AND key=?",
                (self.agent_name, key),
            ).fetchone()
        return json.loads(row[0]) if row else default

    def delete(self, key: str) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "DELETE FROM agent_memory WHERE agent_name=? AND key=?",
                (self.agent_name, key),
            )

    def get_all(self) -> dict[str, object]:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT key, value FROM agent_memory WHERE agent_name=?",
                (self.agent_name,),
            ).fetchall()
        return {key: json.loads(val) for key, val in rows}
