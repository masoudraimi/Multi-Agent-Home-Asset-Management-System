"""Sync/async entry points to the agent runtime.

Two runtimes coexist, chosen by `LLM_PROVIDER`:

    LLM_PROVIDER=claude_cli      → shells out to the Claude Code CLI
                                   (OAuth-based auth, no API key needed).
                                   See `agent/cli_runner.py`.
    LLM_PROVIDER=claude_sdk      → LangGraph specialists via ChatAnthropic
                                   (requires ANTHROPIC_API_KEY).
    LLM_PROVIDER=openrouter      → LangGraph specialists via ChatOpenAI
                                   (requires OPENROUTER_API_KEY).

`run_turn` (sync generator) is retained because `eval/run_eval.py` uses it.
Everything else should call `run_turn_in_loop` directly from an event loop.
"""

from __future__ import annotations

import asyncio
from typing import Generator

from agent.context import ConversationContext  # noqa: F401  (re-export for callers)


def _use_cli() -> bool:
    from core.models import Provider, get_provider
    return get_provider() == Provider.CLAUDE_CLI


def run_turn(
    user_message: str,
    context: ConversationContext,
) -> Generator[dict, None, None]:
    """Synchronous generator wrapper. Spins up an event loop internally."""
    if _use_cli():
        from agent.cli_runner import run_cli_turn
        events = asyncio.run(run_cli_turn(user_message, context))
    else:
        from agents.orchestrator.dispatcher import dispatch_turn
        events = asyncio.run(dispatch_turn(user_message, context))
    yield from events


async def run_turn_in_loop(
    user_message: str,
    context: ConversationContext,
    *,
    thread_id: str | None = None,
    request_id: str | None = None,
) -> list[dict]:
    """Async variant for use inside a running event loop (Reflex, FastAPI).

    thread_id is only used by the LangGraph path (checkpointer thread key).
    The CLI path bypasses LangGraph and doesn't use it.
    """
    if _use_cli():
        from agent.cli_runner import run_cli_turn
        return await run_cli_turn(user_message, context)
    from agents.orchestrator.dispatcher import dispatch_turn
    return await dispatch_turn(
        user_message, context, thread_id=thread_id, request_id=request_id,
    )
