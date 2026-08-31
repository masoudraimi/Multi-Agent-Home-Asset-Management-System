"""Central model definitions, provider selection, and client factories."""

from __future__ import annotations

import os
from enum import Enum

import anthropic


class Provider(str, Enum):
    CLAUDE_SDK = "claude_sdk"
    CLAUDE_CLI = "claude_cli"
    OPENROUTER = "openrouter"


def get_provider() -> Provider:
    return Provider(os.environ.get("LLM_PROVIDER", Provider.CLAUDE_CLI.value))


# Anthropic-native model IDs — used in agent.yaml configs and with the Claude SDK
HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
DEFAULT = SONNET

_MODEL_IDS: dict[Provider, dict[str, str]] = {
    Provider.CLAUDE_SDK: {"haiku": HAIKU, "sonnet": SONNET},
    Provider.CLAUDE_CLI: {"haiku": HAIKU, "sonnet": SONNET},  # CLI uses native Anthropic IDs
    Provider.OPENROUTER: {
        "haiku": "anthropic/claude-haiku-4-5",
        "sonnet": "anthropic/claude-sonnet-4-6",
    },
}


# Context window sizes (tokens) per logical tier — both current Claude tiers
# share 200k, so this is mostly future-proofing/documentation, but it makes
# short-term memory's history budget explainable and correct if a tier's
# context size ever changes.
CONTEXT_WINDOW_TOKENS: dict[str, int] = {
    "haiku": 200_000,
    "sonnet": 200_000,
}


def resolve_model(logical_name: str) -> str:
    """Map 'haiku' or 'sonnet' to the provider-specific model ID.

    Env overrides (apply across all providers):
      LLM_MODEL_FAST  — overrides the 'haiku' tier (orchestrator routing)
      LLM_MODEL_SMART — overrides the 'sonnet' tier (specialist agents)
    """
    env_key = "LLM_MODEL_FAST" if logical_name == "haiku" else "LLM_MODEL_SMART"
    if override := os.environ.get(env_key):
        return override
    return _MODEL_IDS[get_provider()][logical_name]


def anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


def simple_complete(logical_model: str, max_tokens: int, prompt: str) -> str:
    """Single-turn, provider-aware completion. Returns the response text."""
    import json
    import subprocess
    model = resolve_model(logical_model)
    provider = get_provider()

    if provider == Provider.CLAUDE_CLI:
        result = subprocess.run(
            ["claude", "--model", model, "--output-format", "json", "-p", prompt],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(result.stdout)
        return data.get("result", "")

    if provider == Provider.OPENROUTER:
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
