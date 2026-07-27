"""Asset deletion workflow: fetches asset details and requests human approval."""

from __future__ import annotations

from core.event_bus import EventBus
from core.events import HumanApprovalRequested
from core.observability import audit_log
from core.session import get_current_user_id
from db import get_provider


def review_delete_asset(asset_id: int) -> dict:
    """Fetch the asset, then publish a HumanApprovalRequested event.

    The approval card in the UI shows the asset details so the user can
    confirm before delete_asset runs. delete_asset should only be called
    after the user confirms via that card.
    """
    provider = get_provider()
    user_id = get_current_user_id()
    history = provider.get_asset_history(user_id, asset_id)
    asset = history.get("asset")
    if not asset:
        return {"status": "not_found", "asset_id": asset_id}

    maint_count = history.get("maintenance_count", 0)
    request_id = f"del-{asset_id}"

    EventBus().publish(HumanApprovalRequested(
        request_id=request_id,
        agent_name="asset",
        action_description=(
            f"Delete asset: {asset.get('name', 'unnamed')} "
            f"(id={asset_id}). This will also remove {maint_count} "
            f"maintenance record(s)."
        ),
        payload={
            "asset_id": asset_id,
            "name": asset.get("name", ""),
            "category": asset.get("category", ""),
            "location": asset.get("location", ""),
            "maintenance_records_to_delete": maint_count,
        },
    ))
    audit_log("delete_approval_requested", {
        "request_id": request_id,
        "asset_id": asset_id,
        "asset_name": asset.get("name", ""),
        "maintenance_count": maint_count,
    })

    return {
        "status": "approval_requested",
        "asset_id": asset_id,
        "asset_name": asset.get("name", ""),
        "maintenance_records_to_delete": maint_count,
    }
