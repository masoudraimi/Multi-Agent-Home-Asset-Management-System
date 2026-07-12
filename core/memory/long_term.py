"""Long-term memory: per-user key-value store, backed by the agent_memory table.

Each entry is scoped to the current authenticated user so memories never leak
across users. Uniqueness is (user_id, agent_name, key).
"""

from __future__ import annotations

import json
from datetime import datetime

from core.session import get_current_user_id
from db import get_provider


class LongTermMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def set(self, key: str, value: object) -> None:
        get_provider().memory_set(
            user_id=get_current_user_id(),
            agent_name=self.agent_name,
            key=key,
            value=json.dumps(value),
            updated_at=datetime.now().isoformat(),
        )

    def get(self, key: str, default: object = None) -> object:
        raw = get_provider().memory_get(get_current_user_id(), self.agent_name, key)
        return json.loads(raw) if raw is not None else default

    def delete(self, key: str) -> None:
        get_provider().memory_delete(get_current_user_id(), self.agent_name, key)

    def get_all(self) -> dict[str, object]:
        rows = get_provider().memory_get_all(get_current_user_id(), self.agent_name)
        return {row["key"]: json.loads(row["value"]) for row in rows}
