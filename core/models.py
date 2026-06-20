"""Central model definitions and Anthropic client factory."""

from __future__ import annotations

import os

import anthropic

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"

DEFAULT = SONNET


def anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
