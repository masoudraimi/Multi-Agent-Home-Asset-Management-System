"""MCP server: expose all home asset tools to the claude-agent-sdk.

Creates an in-process SDK MCP server using create_sdk_mcp_server.
Each tool wraps a function from tools/db.py with an async handler.
"""

from __future__ import annotations

from typing import Optional

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server, tool
from pydantic import BaseModel

import tools.db as db


# ---------------------------------------------------------------------------
# Input schemas (Pydantic models used as input_schema for each tool)
# ---------------------------------------------------------------------------

class AddAssetInput(BaseModel):
    name: str
    category: str
    brand: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None
    warranty_expiry: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    plant_species: Optional[str] = None
    plant_size: Optional[str] = None
    planting_date: Optional[str] = None
    plant_notes: Optional[str] = None


class ListAssetsInput(BaseModel):
    category: Optional[str] = None


class SearchAssetsInput(BaseModel):
    query: str


class LogMaintenanceInput(BaseModel):
    asset_id: int
    task_name: str
    completed_date: Optional[str] = None
    cost: Optional[float] = None
    notes: Optional[str] = None
    next_due_date: Optional[str] = None
    interval_days: Optional[int] = None


class GetUpcomingMaintenanceInput(BaseModel):
    days_ahead: int = 30


class GetAssetHistoryInput(BaseModel):
    asset_id: int


class UpdateAssetInput(BaseModel):
    asset_id: int
    name: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None
    warranty_expiry: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    plant_species: Optional[str] = None
    plant_size: Optional[str] = None
    planting_date: Optional[str] = None
    plant_notes: Optional[str] = None


class GetOnboardingQuestionsInput(BaseModel):
    asset_type: str


class ReviewAssetDraftInput(BaseModel):
    draft_json: str


class GetPlantCareScheduleInput(BaseModel):
    asset_id: int


class SuggestMissingAssetsInput(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Tool handlers (async wrappers around synchronous db functions)
# ---------------------------------------------------------------------------

@tool(
    name="add_asset",
    description="Register a new home asset. Use after completing interactive onboarding. "
                "Category must be one of: appliances, HVAC, plumbing, electrical, exterior, "
                "vehicle, garden, plants_trees, other.",
    input_schema=AddAssetInput,
)
async def _add_asset(params: AddAssetInput) -> dict:
    return db.add_asset(**params.model_dump(exclude_none=True))


@tool(
    name="list_assets",
    description="List all home assets, optionally filtered by category.",
    input_schema=ListAssetsInput,
)
async def _list_assets(params: ListAssetsInput) -> dict:
    return db.list_assets(category=params.category)


@tool(
    name="search_assets",
    description="Search assets by name, brand, model, species, or notes.",
    input_schema=SearchAssetsInput,
)
async def _search_assets(params: SearchAssetsInput) -> dict:
    return db.search_assets(query=params.query)


@tool(
    name="log_maintenance",
    description="Record a completed maintenance task. Sets next_due_date for future reminders.",
    input_schema=LogMaintenanceInput,
)
async def _log_maintenance(params: LogMaintenanceInput) -> dict:
    return db.log_maintenance(**params.model_dump(exclude_none=True))


@tool(
    name="get_upcoming_maintenance",
    description="Get all maintenance tasks due within the next N days, including overdue ones.",
    input_schema=GetUpcomingMaintenanceInput,
)
async def _get_upcoming_maintenance(params: GetUpcomingMaintenanceInput) -> dict:
    return db.get_upcoming_maintenance(days_ahead=params.days_ahead)


@tool(
    name="get_asset_history",
    description="Get the full maintenance history and total spend for a specific asset.",
    input_schema=GetAssetHistoryInput,
)
async def _get_asset_history(params: GetAssetHistoryInput) -> dict:
    return db.get_asset_history(asset_id=params.asset_id)


@tool(
    name="update_asset",
    description="Update one or more fields on an existing asset.",
    input_schema=UpdateAssetInput,
)
async def _update_asset(params: UpdateAssetInput) -> dict:
    return db.update_asset(**params.model_dump(exclude_none=True))


@tool(
    name="get_onboarding_questions",
    description="Get type-specific guided questions for onboarding a new asset. "
                "Call this at the start of any 'add new asset' workflow.",
    input_schema=GetOnboardingQuestionsInput,
)
async def _get_onboarding_questions(params: GetOnboardingQuestionsInput) -> dict:
    return db.get_onboarding_questions(asset_type=params.asset_type)


@tool(
    name="review_asset_draft",
    description="LLM-as-judge: review a partially-filled asset before saving. "
                "Returns confidence score, missing fields, and suggestions.",
    input_schema=ReviewAssetDraftInput,
)
async def _review_asset_draft(params: ReviewAssetDraftInput) -> dict:
    return db.review_asset_draft(draft_json=params.draft_json)


@tool(
    name="get_plant_care_schedule",
    description="Get a species-specific care schedule for a plant or tree asset. "
                "Returns upcoming tasks: fertilise, prune, pest check, water, etc.",
    input_schema=GetPlantCareScheduleInput,
)
async def _get_plant_care_schedule(params: GetPlantCareScheduleInput) -> dict:
    return db.get_plant_care_schedule(asset_id=params.asset_id)


@tool(
    name="suggest_missing_assets",
    description="Suggest commonly-missed home assets by comparing the database to a "
                "comprehensive checklist. Returns gaps grouped by priority.",
    input_schema=SuggestMissingAssetsInput,
)
async def _suggest_missing_assets(params: SuggestMissingAssetsInput) -> dict:
    return db.suggest_missing_assets()


# ---------------------------------------------------------------------------
# OpenRouter: tool schemas and direct dispatch (bypasses MCP)
# ---------------------------------------------------------------------------

_OPENROUTER_TOOL_DEFS: list[tuple[str, str, type[BaseModel]]] = [
    ("add_asset",
     "Register a new home asset. Use after completing interactive onboarding. "
     "Category must be one of: appliances, HVAC, plumbing, electrical, exterior, "
     "vehicle, garden, plants_trees, other.",
     AddAssetInput),
    ("list_assets",
     "List all home assets, optionally filtered by category.",
     ListAssetsInput),
    ("search_assets",
     "Search assets by name, brand, model, species, or notes.",
     SearchAssetsInput),
    ("log_maintenance",
     "Record a completed maintenance task. Sets next_due_date for future reminders.",
     LogMaintenanceInput),
    ("get_upcoming_maintenance",
     "Get all maintenance tasks due within the next N days, including overdue ones.",
     GetUpcomingMaintenanceInput),
    ("get_asset_history",
     "Get the full maintenance history and total spend for a specific asset.",
     GetAssetHistoryInput),
    ("update_asset",
     "Update one or more fields on an existing asset.",
     UpdateAssetInput),
    ("get_onboarding_questions",
     "Get type-specific guided questions for onboarding a new asset. "
     "Call this at the start of any 'add new asset' workflow.",
     GetOnboardingQuestionsInput),
    ("review_asset_draft",
     "LLM-as-judge: review a partially-filled asset before saving. "
     "Returns confidence score, missing fields, and suggestions.",
     ReviewAssetDraftInput),
    ("get_plant_care_schedule",
     "Get a species-specific care schedule for a plant or tree asset. "
     "Returns upcoming tasks: fertilise, prune, pest check, water, etc.",
     GetPlantCareScheduleInput),
    ("suggest_missing_assets",
     "Suggest commonly-missed home assets by comparing the database to a "
     "comprehensive checklist. Returns gaps grouped by priority.",
     SuggestMissingAssetsInput),
]


def get_openai_tool_schemas() -> list[dict]:
    """Return tool definitions in OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": schema_cls.model_json_schema(),
            },
        }
        for name, desc, schema_cls in _OPENROUTER_TOOL_DEFS
    ]


def dispatch_tool(name: str, args: dict) -> dict:
    """Execute a tool by name with a raw args dict. Used by the OpenRouter agent loop."""
    schema_map = {t[0]: t[2] for t in _OPENROUTER_TOOL_DEFS}
    params = schema_map[name](**args)
    match name:
        case "add_asset":
            return db.add_asset(**params.model_dump(exclude_none=True))
        case "list_assets":
            return db.list_assets(category=params.category)
        case "search_assets":
            return db.search_assets(query=params.query)
        case "log_maintenance":
            return db.log_maintenance(**params.model_dump(exclude_none=True))
        case "get_upcoming_maintenance":
            return db.get_upcoming_maintenance(days_ahead=params.days_ahead)
        case "get_asset_history":
            return db.get_asset_history(asset_id=params.asset_id)
        case "update_asset":
            return db.update_asset(**params.model_dump(exclude_none=True))
        case "get_onboarding_questions":
            return db.get_onboarding_questions(asset_type=params.asset_type)
        case "review_asset_draft":
            return db.review_asset_draft(draft_json=params.draft_json)
        case "get_plant_care_schedule":
            return db.get_plant_care_schedule(asset_id=params.asset_id)
        case "suggest_missing_assets":
            return db.suggest_missing_assets()
        case _:
            raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

def build_sdk_server():
    """Create and return an McpSdkServerConfig for use in ClaudeAgentOptions."""
    tools: list[SdkMcpTool] = [
        _add_asset,
        _list_assets,
        _search_assets,
        _log_maintenance,
        _get_upcoming_maintenance,
        _get_asset_history,
        _update_asset,
        _get_onboarding_questions,
        _review_asset_draft,
        _get_plant_care_schedule,
        _suggest_missing_assets,
    ]
    return create_sdk_mcp_server("home-assets", tools=tools)
