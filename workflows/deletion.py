"""Backward-compatibility shim. Logic lives in agents/asset/workflows/deletion.py."""

from agents.asset.workflows.deletion import review_delete_asset  # noqa: F401

__all__ = ["review_delete_asset"]
