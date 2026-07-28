"""stdio MCP server exposing our tools to the Claude Code CLI subprocess.

Loaded by `agent/cli_runner.py` via `claude --mcp-config` when
`LLM_PROVIDER=claude_cli`. The CLI's LLM sees these tools with the same
Pydantic-derived schemas that the LangGraph path uses (via `tools/schemas.py`),
so the tool contract is single-sourced.

The subprocess doesn't inherit the parent's `current_user` ContextVar (that's
async/thread-local, not process-local), so we re-apply it from the
`HOME_ASSET_USER_ID` env var that the CLI runner sets when spawning.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Callable

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel

import tools.db as db
from core.session import USER_ID_ENV_VAR, set_current_user
from tools import schemas

# ── Tool registry: (name, description, schema, handler) ──────────────────
# Keep the descriptions in sync with the LangChain @tool docstrings in
# tools/langchain_tools.py — the CLI-side LLM sees these, not those.

_TOOLS: list[tuple[str, str, type[BaseModel], Callable[..., dict]]] = [
    ("add_asset",
     "Register a new home asset. Category must be one of: appliances, HVAC, plumbing, "
     "electrical, exterior, vehicle, garden, plants_trees, other.",
     schemas.AddAssetInput, db.add_asset),
    ("list_assets", "List all home assets, optionally filtered by category.",
     schemas.ListAssetsInput, db.list_assets),
    ("search_assets", "Search assets by name, brand, model, species, or notes.",
     schemas.SearchAssetsInput, db.search_assets),
    ("get_asset_history",
     "Get the full maintenance history and total cost for a specific asset.",
     schemas.GetAssetHistoryInput, db.get_asset_history),
    ("get_upcoming_maintenance",
     "Maintenance tasks due within the next N days, including overdue ones.",
     schemas.GetUpcomingMaintenanceInput, db.get_upcoming_maintenance),
    ("get_expiring_warranties",
     "Assets whose warranty expires within the next N days.",
     schemas.GetExpiringWarrantiesInput, db.get_expiring_warranties),
    ("get_plant_care_schedule",
     "Species-specific care schedule for a plant/tree asset.",
     schemas.GetPlantCareScheduleInput, db.get_plant_care_schedule),
    ("get_onboarding_questions",
     "Guided onboarding questions for a specific asset type.",
     schemas.GetOnboardingQuestionsInput, db.get_onboarding_questions),
    ("suggest_missing_assets",
     "Suggest commonly-missed home assets versus a comprehensive checklist.",
     schemas.SuggestMissingAssetsInput, db.suggest_missing_assets),
    ("update_asset", "Update one or more fields on an existing asset.",
     schemas.UpdateAssetInput, db.update_asset),
    ("log_maintenance", "Record a completed or scheduled maintenance task.",
     schemas.LogMaintenanceInput, db.log_maintenance),
    ("review_asset_draft",
     "LLM-as-judge: review a partially-filled asset draft before saving.",
     schemas.ReviewAssetDraftInput, db.review_asset_draft),
    ("review_delete_asset",
     "Fetch an asset's details and request user approval before deletion.",
     schemas.ReviewDeleteAssetInput, db.review_delete_asset),
    ("delete_asset",
     "Permanently delete an asset. Only call after review_delete_asset + user confirms.",
     schemas.DeleteAssetInput, db.delete_asset),
]


def _dispatch(name: str, args: dict[str, Any]) -> dict:
    for tool_name, _desc, schema_cls, fn in _TOOLS:
        if tool_name == name:
            validated = schema_cls(**args)
            return fn(**validated.model_dump(exclude_none=True))
    raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    # Subprocess boundary: re-apply the current-user ContextVar from env var.
    if uid := os.environ.get(USER_ID_ENV_VAR):
        set_current_user(uid)

    server: Server = Server("home-assets")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(name=name, description=desc, inputSchema=schema_cls.model_json_schema())
            for name, desc, schema_cls, _ in _TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            result = _dispatch(name, arguments)
        except Exception as exc:
            result = {"error": str(exc)}
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)
