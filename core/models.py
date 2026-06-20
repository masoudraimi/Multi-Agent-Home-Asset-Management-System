"""Central model definitions, provider selection, and client factories."""

from __future__ import annotations

import os
from enum import Enum

import anthropic


class Provider(str, Enum):
    CLAUDE_SDK = "claude_sdk"
    OPENROUTER = "openrouter"


def get_provider() -> Provider:
    return Provider(os.environ.get("LLM_PROVIDER", Provider.CLAUDE_SDK.value))


# Anthropic-native model IDs — used in agent.yaml configs and with the Claude SDK
HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
DEFAULT = SONNET

_MODEL_IDS: dict[Provider, dict[str, str]] = {
    Provider.CLAUDE_SDK: {
        "haiku": HAIKU,
        "sonnet": SONNET,
    },
    Provider.OPENROUTER: {
        "haiku": "anthropic/claude-haiku-4-5",
        "sonnet": "anthropic/claude-sonnet-4-6",
    },
}


def resolve_model(logical_name: str) -> str:
    """Map 'haiku' or 'sonnet' to the provider-specific model ID."""
    return _MODEL_IDS[get_provider()][logical_name]


def anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


def simple_complete(logical_model: str, max_tokens: int, prompt: str) -> str:
    """Single-turn, provider-aware completion. Returns the response text."""
    model = resolve_model(logical_model)
    if get_provider() == Provider.OPENROUTER:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            base_url="https://openrouter.ai/api/v1",
        )
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()

    resp = anthropic_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()
