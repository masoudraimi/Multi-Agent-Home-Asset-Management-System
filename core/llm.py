"""Provider-aware ChatModel factory for LangGraph specialists.

Reads `LLM_PROVIDER` from the environment (same knob as `core.models`) and
returns the appropriate LangChain chat model. Overrides via `LLM_MODEL_FAST`
and `LLM_MODEL_SMART` also honoured — same semantics as `core.models`.

Provider paths supported:
    LLM_PROVIDER=claude_sdk      → langchain_anthropic.ChatAnthropic
    LLM_PROVIDER=openrouter      → langchain_openai.ChatOpenAI with base_url
    LLM_PROVIDER=claude_cli      → not supported (LangGraph replaces the CLI path)

The CLI provider from BaseAgent is intentionally dropped here — it exists
only for the pre-LangGraph fallback and is scheduled for removal in Phase 6.
"""

from __future__ import annotations

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from core.models import Provider, get_provider, resolve_model


class UnsupportedProviderError(RuntimeError):
    """LLM_PROVIDER is set to a value that LangGraph specialists don't support."""


def build_chat_model(
    tier: str = "sonnet",
    *,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout_s: float = 30.0,
) -> BaseChatModel:
    """Return a LangChain ChatModel wired for the active provider.

    tier: "haiku" (fast) or "sonnet" (smart). Resolved via `core.models.resolve_model`.
    """
    provider = get_provider()
    model = resolve_model(tier)

    if provider == Provider.OPENROUTER:
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout_s,
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            base_url="https://openrouter.ai/api/v1",
        )

    if provider in (Provider.CLAUDE_SDK, Provider.CLAUDE_CLI):
        # Both SDK and CLI paths of the old BaseAgent map to native Anthropic
        # in the LangGraph world. CLI subprocess is dropped.
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout_s,
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )

    raise UnsupportedProviderError(
        f"LLM_PROVIDER={provider.value} not supported by LangGraph specialists. "
        "Set LLM_PROVIDER=claude_sdk or openrouter."
    )
