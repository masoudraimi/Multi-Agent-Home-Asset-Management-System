"""LangChain @tool wrappers over `tools/db.py`.

Single source of truth for tools used by any LangGraph specialist subgraph.
Each wrapper:
  * reuses the Pydantic schemas from `tools/mcp_server.py` (no duplication)
  * calls the plain sync function in `tools/db.py`
  * emits a `tool_call` metric with outcome=success|error
  * emits structured logs on entry, exit, and failure

Errors propagate — the surrounding LangGraph `ToolNode` decides whether to
feed the error back to the LLM (default) or bail. Do not catch and swallow.

Import `TOOLS` (a list of `BaseTool`) and bind it directly:

    from tools.langchain_tools import TOOLS
    llm_with_tools = ChatAnthropic(...).bind_tools(TOOLS)
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool

import tools.db as db
from core.logging import get_logger
from core.metrics import emit_tool_call
from tools.mcp_server import (
    AddAssetInput,
    DeleteAssetInput,
    GetAssetHistoryInput,
    GetExpiringWarrantiesInput,
    GetOnboardingQuestionsInput,
    GetPlantCareScheduleInput,
    GetUpcomingMaintenanceInput,
    ListAssetsInput,
    LogMaintenanceInput,
    ReviewAssetDraftInput,
    ReviewDeleteAssetInput,
    SearchAssetsInput,
    SuggestMissingAssetsInput,
    UpdateAssetInput,
)

log = get_logger(__name__)


def _call(name: str, fn: Any, **kwargs: Any) -> Any:
    """Log + metric + error passthrough for a single db-tool invocation."""
    log.info("tool_call_started", tool=name, arg_keys=sorted(kwargs.keys()))
    try:
        result = fn(**kwargs)
    except Exception:
        emit_tool_call(name, "error")
        log.exception("tool_call_failed", tool=name)
        raise
    emit_tool_call(name, "success")
    log.info("tool_call_finished", tool=name)
    return result


# ── Read tools ─────────────────────────────────────────────────────────────

@tool("list_assets", args_schema=ListAssetsInput)
def list_assets(**kwargs: Any) -> dict:
    """List all home assets, optionally filtered by category.

    category: Optional filter — one of appliances, HVAC, plumbing, electrical,
    exterior, vehicle, garden, plants_trees, other.
    """
    return _call("list_assets", db.list_assets, **kwargs)


@tool("search_assets", args_schema=SearchAssetsInput)
def search_assets(**kwargs: Any) -> dict:
    """Search for assets by name, brand, model, species, or notes.

    query: Search term to match against asset fields.
    """
    return _call("search_assets", db.search_assets, **kwargs)


@tool("get_asset_history", args_schema=GetAssetHistoryInput)
def get_asset_history(**kwargs: Any) -> dict:
    """Get the full maintenance history and total cost for a specific asset.

    asset_id: ID of the asset.
    """
    return _call("get_asset_history", db.get_asset_history, **kwargs)


@tool("get_upcoming_maintenance", args_schema=GetUpcomingMaintenanceInput)
def get_upcoming_maintenance(**kwargs: Any) -> dict:
    """Get maintenance tasks due within the next N days, including overdue ones.

    days_ahead: Number of days to look ahead (default 30).
    """
    return _call("get_upcoming_maintenance", db.get_upcoming_maintenance, **kwargs)


@tool("get_expiring_warranties", args_schema=GetExpiringWarrantiesInput)
def get_expiring_warranties(**kwargs: Any) -> dict:
    """Find assets whose warranty expires within the next N days.

    days_ahead: How many days forward to look (default 90).
    """
    return _call("get_expiring_warranties", db.get_expiring_warranties, **kwargs)


@tool("get_plant_care_schedule", args_schema=GetPlantCareScheduleInput)
def get_plant_care_schedule(**kwargs: Any) -> dict:
    """Get a species-specific care schedule for a plant or tree asset.

    asset_id: ID of the plant/tree asset.
    """
    return _call("get_plant_care_schedule", db.get_plant_care_schedule, **kwargs)


@tool("get_onboarding_questions", args_schema=GetOnboardingQuestionsInput)
def get_onboarding_questions(**kwargs: Any) -> dict:
    """Get guided onboarding questions for a specific asset type.

    asset_type: The category of asset being added (e.g. 'appliances', 'plant', 'HVAC').
    """
    return _call("get_onboarding_questions", db.get_onboarding_questions, **kwargs)


@tool("suggest_missing_assets", args_schema=SuggestMissingAssetsInput)
def suggest_missing_assets(**kwargs: Any) -> dict:
    """Suggest commonly-missed home assets by comparing your database to a comprehensive checklist."""
    return _call("suggest_missing_assets", db.suggest_missing_assets, **kwargs)


# ── Write tools ────────────────────────────────────────────────────────────

@tool("add_asset", args_schema=AddAssetInput)
def add_asset(**kwargs: Any) -> dict:
    """Register a new home asset in the database.

    See AddAssetInput for the full field list. Category must be one of:
    appliances, HVAC, plumbing, electrical, exterior, vehicle, garden,
    plants_trees, other.
    """
    return _call("add_asset", db.add_asset, **kwargs)


@tool("update_asset", args_schema=UpdateAssetInput)
def update_asset(**kwargs: Any) -> dict:
    """Update one or more fields on an existing asset.

    asset_id is required. Any other field passed as non-null becomes an update.
    """
    return _call("update_asset", db.update_asset, **kwargs)


@tool("log_maintenance", args_schema=LogMaintenanceInput)
def log_maintenance(**kwargs: Any) -> dict:
    """Record a completed or scheduled maintenance task for an asset.

    asset_id: ID of the asset.
    task_name: Description of the task, e.g. 'Filter replacement'.
    completed_date: ISO date YYYY-MM-DD when done (defaults to today).
    cost: Cost in dollars.
    notes: Notes about the work.
    next_due_date: ISO date when this task is next due.
    interval_days: Recurring interval in days.
    """
    return _call("log_maintenance", db.log_maintenance, **kwargs)


# ── Review / approval-gated tools ──────────────────────────────────────────
# review_delete_asset is called BEFORE the interrupt() node; delete_asset
# runs only after the user resumes with Command(resume={"approved": True}).

@tool("review_asset_draft", args_schema=ReviewAssetDraftInput)
def review_asset_draft(**kwargs: Any) -> dict:
    """LLM-as-judge: review a partially-filled asset draft before saving.

    draft_json: JSON string of the asset fields collected so far.
    """
    return _call("review_asset_draft", db.review_asset_draft, **kwargs)


@tool("review_delete_asset", args_schema=ReviewDeleteAssetInput)
def review_delete_asset(**kwargs: Any) -> dict:
    """Fetch an asset's details and prepare an approval payload before deletion.

    In the LangGraph path this precedes an `interrupt()` node — the caller
    graph should NOT invoke `delete_asset` unless the user resumes with
    approval. See agents/asset/graph.py:await_approval.

    asset_id: ID of the asset the user wants to delete.
    """
    return _call("review_delete_asset", db.review_delete_asset, **kwargs)


@tool("delete_asset", args_schema=DeleteAssetInput)
def delete_asset(**kwargs: Any) -> dict:
    """Permanently delete an asset and its maintenance history.

    Only call after the user has resumed with approval via the interrupt in
    agents/asset/graph.py. Maintenance_tasks cascades via ON DELETE.

    asset_id: ID of the asset to delete.
    """
    return _call("delete_asset", db.delete_asset, **kwargs)


# ── Registry ──────────────────────────────────────────────────────────────
# Order matches the categorisation above for readability in system prompts.
TOOLS: list[BaseTool] = [
    list_assets,
    search_assets,
    get_asset_history,
    get_upcoming_maintenance,
    get_expiring_warranties,
    get_plant_care_schedule,
    get_onboarding_questions,
    suggest_missing_assets,
    add_asset,
    update_asset,
    log_maintenance,
    review_asset_draft,
    review_delete_asset,
    delete_asset,
]

TOOLS_BY_NAME: dict[str, BaseTool] = {t.name: t for t in TOOLS}
