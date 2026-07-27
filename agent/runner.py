"""Backward-compatibility shim. The agent runner now lives in agents/asset/agent.py.

run_turn() wraps OrchestratorAgent.run_turn() in a synchronous generator so that
components/chat_tab.py works without modification.

run_turn_in_loop() is the async-native variant for frameworks (Reflex, FastAPI)
that already run an asyncio event loop — it awaits _dispatch_async directly,
bypassing the asyncio.run() wrapper in run_turn().
"""

from __future__ import annotations

from typing import Generator

from agent.context import ConversationContext  # noqa: F401


def run_turn(
    user_message: str,
    context: ConversationContext,
) -> Generator[dict, None, None]:
    """Synchronous generator shim. Delegates to OrchestratorAgent."""
    from agents.orchestrator.agent import OrchestratorAgent
    agent = OrchestratorAgent()
    yield from agent.run_turn(user_message, context)


async def run_turn_in_loop(
    user_message: str,
    context: ConversationContext,
) -> list[dict]:
    """Async variant for use inside a running event loop (Reflex, FastAPI, etc.).

    Calls OrchestratorAgent._dispatch_async directly, which avoids the
    asyncio.run() call inside run_turn() that would raise RuntimeError when
    an event loop is already running.

    Returns all events as a list (same structure as run_turn yields).
    """
    from agents.orchestrator.agent import OrchestratorAgent

    agent = OrchestratorAgent()

    if agent.guardrails.is_injected(user_message):
        return [{"type": "assistant_text", "content": "I cannot process that request."}]

    events: list[dict] = []
    await agent._dispatch_async(user_message, context, events)
    return events
