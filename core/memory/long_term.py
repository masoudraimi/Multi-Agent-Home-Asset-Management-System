"""Long-term memory: key-value store per agent, backed by the agent_memory table."""

from __future__ import annotations

import json
from datetime import datetime

from db_conn import get_client


class LongTermMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def set(self, key: str, value: object) -> None:
        get_client().table("agent_memory").upsert(
            {
                "agent_name": self.agent_name,
                "key": key,
                "value": json.dumps(value),
                "updated_at": datetime.now().isoformat(),
            },
            on_conflict="agent_name,key",
        ).execute()

    def get(self, key: str, default: object = None) -> object:
        rows = (
            get_client()
            .table("agent_memory")
            .select("value")
            .eq("agent_name", self.agent_name)
            .eq("key", key)
            .execute()
            .data
        )
        return json.loads(rows[0]["value"]) if rows else default

    def delete(self, key: str) -> None:
        get_client().table("agent_memory").delete().eq("agent_name", self.agent_name).eq("key", key).execute()

    def get_all(self) -> dict[str, object]:
        rows = (
            get_client()
            .table("agent_memory")
            .select("key, value")
            .eq("agent_name", self.agent_name)
            .execute()
            .data
        )
        return {row["key"]: json.loads(row["value"]) for row in rows}
