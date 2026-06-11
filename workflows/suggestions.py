"""Backward-compatibility shim. Logic lives in agents/asset/workflows/suggestions.py."""

from agents.asset.workflows.suggestions import (  # noqa: F401
    suggest_missing_assets,
)

__all__ = ["suggest_missing_assets"]
