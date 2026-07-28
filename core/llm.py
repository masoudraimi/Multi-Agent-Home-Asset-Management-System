"""Provider-aware ChatModel factory for LangGraph specialists.

Reads `LLM_PROVIDER` from the environment (same knob as `core.models`) and
returns the appropriate LangChain chat model. Overrides via `LLM_MODEL_FAST`
and `LLM_MODEL_SMART` also honoured — same semantics as `core.models`.

Supported providers via this module:
    LLM_PROVIDER=claude_sdk   → langchain_anthropic.ChatAnthropic
                               (requires ANTHROPIC_API_KEY)
    LLM_PROVIDER=openrouter   → langchain_openai.ChatOpenAI via OpenRouter
                               (requires OPENROUTER_API_KEY)

`LLM_PROVIDER=claude_cli` is handled by `agent/cli_runner.py` — it bypasses
LangGraph and shells out to the Claude Code CLI directly for OAuth-based
auth. If the CLI provider reaches this factory it means the router in
`agent/runner.py` failed to short-circuit, so raise loudly.

Missing/blank credentials raise `MissingCredentialsError` with the exact env
var to set, before any HTTP call — so failures surface at graph build time
rather than deep in an LLM invocation stack trace.
"""

from __future__ import annotations

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from core.models import Provider, get_provider, resolve_model


class UnsupportedProviderError(RuntimeError):
    """LLM_PROVIDER is set to a value that LangGraph specialists don't support."""


class MissingCredentialsError(RuntimeError):
    """The active provider needs an API key that isn't in the environment."""


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
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise MissingCredentialsError(
                "LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set. "
                "Add it to your .env or switch to LLM_PROVIDER=claude_sdk."
            )
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout_s,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    if provider == Provider.CLAUDE_SDK:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise MissingCredentialsError(
                "LLM_PROVIDER=claude_sdk but ANTHROPIC_API_KEY is not set. "
                "Add ANTHROPIC_API_KEY to your .env, or switch to "
                "LLM_PROVIDER=openrouter (with OPENROUTER_API_KEY), or "
                "LLM_PROVIDER=claude_cli (uses your Claude Code OAuth session)."
            )
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout_s,
            api_key=api_key,
        )

    if provider == Provider.CLAUDE_CLI:
        # Should never happen — agent/runner.py routes CLI turns to cli_runner.
        raise UnsupportedProviderError(
            "LLM_PROVIDER=claude_cli reached the LangGraph LLM factory. "
            "This is a routing bug: check agent/runner.py::_use_cli."
        )

    raise UnsupportedProviderError(
        f"LLM_PROVIDER={provider.value} not supported. "
        "Set LLM_PROVIDER to claude_cli, claude_sdk, or openrouter."
    )
