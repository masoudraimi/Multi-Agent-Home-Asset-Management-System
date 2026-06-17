"""AssetAgent: inventory CRUD, guided onboarding, and asset gap suggestions."""

from __future__ import annotations

from core.base_agent import BaseAgent


class AssetAgent(BaseAgent):
    agent_name = "asset"
