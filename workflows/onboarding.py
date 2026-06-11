"""Backward-compatibility shim. Logic lives in agents/asset/workflows/onboarding.py."""

from agents.asset.workflows.onboarding import (  # noqa: F401
    get_onboarding_questions,
    review_asset_draft,
)

__all__ = ["get_onboarding_questions", "review_asset_draft"]
