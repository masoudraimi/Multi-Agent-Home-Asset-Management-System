"""Backward-compatibility shim. The agent runner now lives in agents/asset/agent.py.

run_turn() wraps AssetAgent.run_turn() in a synchronous generator so that
components/chat_tab.py works without modification.
"""

from __future__ import annotations

from typing import Generator

from agent.context import ConversationContext  # noqa: F401


MODEL = "claude-sonnet-4-6"


def run_turn(
    user_message: str,
    context: ConversationContext,
) -> Generator[dict, None, None]:
    """Synchronous generator shim. Delegates to OrchestratorAgent."""
    from agents.orchestrator.agent import OrchestratorAgent
    agent = OrchestratorAgent()
    yield from agent.run_turn(user_message, context)
